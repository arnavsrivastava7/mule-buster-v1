"""Bank AI end-to-end pipeline.

Load raw CSV files -> build weekly snapshots -> label -> split ->
train LogReg + LightGBM -> evaluate -> score latest snapshot ->
write bank_ai_results.csv and bank_alerts.csv.
"""
from pathlib import Path
from datetime import datetime, timezone
import json as _json

import numpy as np
import pandas as pd

from bank_ai.config import load_config
from bank_ai.data.loaders import load_and_validate
from bank_ai.features.build import ML_FEATURES
from bank_ai.models.dataset import (
    make_snapshots,
    label_snapshots,
    group_split,
)
from bank_ai.models.train import train_models, save_artifacts, load_artifacts
from bank_ai.models.explain import ModelExplainer
from bank_ai.eval.report import evaluate_all_models, format_comparison_table
from bank_ai.scoring.blend import blend_scores, assign_band
from bank_ai.scoring.merchant_guard import merchant_adjustment
from bank_ai.scoring.reason_codes import build_reason_codes, insufficient_data_reason
from bank_ai.rules.baseline import score_rules
from bank_ai.schemas import AccountRiskResult, DISCLAIMER


def _run_training(txns, accounts, labels, cfg, artifact_dir):
    snapshot_df = make_snapshots(txns, accounts, cfg)
    labeled_df, _ = label_snapshots(snapshot_df, labels, cfg)
    train_df, val_df, test_df = group_split(labeled_df, cfg)
    trained = train_models(train_df, cfg, val_df=val_df)
    save_artifacts(trained, artifact_dir)
    return trained, test_df


def _run_evaluation(trained, test_df, cfg):
    results = evaluate_all_models(test_df, trained, cfg)
    return format_comparison_table(results), results


def _score_latest_snapshot(txns, accounts, cfg, trained):
    latest_as_of = max(pd.to_datetime(txns["ts"], utc=True))
    snapshot_df = make_snapshots(txns, accounts, cfg, as_of_dates=[latest_as_of])
    rows = []
    alerts = []
    now_str = datetime.now(timezone.utc).isoformat()

    for row in snapshot_df.itertuples():
        gated = bool(
            getattr(row, "txn_count_7d", 0) < cfg.min_txn_7d
            or getattr(row, "total_in_7d", 0.0) < cfg.min_in_value
        )
        if gated:
            reason_codes = insufficient_data_reason(row, cfg)
            final_score = 0
            band, action = assign_band(final_score, cfg)
            r_score = 0
            m_score = 0
            adj = 0
        else:
            r_score, fired_rules = score_rules(row, cfg)
            ml_prob = trained.predict_lgbm_proba(
                pd.DataFrame([{f: float(getattr(row, f, 0.0)) for f in ML_FEATURES}])
            )[0]
            adj, blocked, _ = merchant_adjustment(row, cfg)
            m_score, final_score = blend_scores(ml_prob, r_score, adj, cfg)
            band, action = assign_band(final_score, cfg)
            explainer = ModelExplainer(trained.lgbm, list(ML_FEATURES))
            shap_top = explainer.top_contributors(row, top_k=3)
            reason_codes = build_reason_codes(fired_rules, shap_top, row, cfg, adj)

        result = AccountRiskResult(
            schema_version="1.0",
            run_id=f"run_{now_str}",
            model_version="lgbm_v1+rules_v1",
            account_id=row.account_id,
            as_of=latest_as_of,
            risk_score=int(final_score),
            risk_band=band,
            rule_score=int(r_score),
            ml_score=int(m_score),
            merchant_adjustment=int(adj),
            recommended_action=action,
            reason_codes=reason_codes,
            features={f: float(getattr(row, f, 0.0)) for f in ML_FEATURES},
            flags={"gated": gated, "suppressed_by_feedback": False},
        )
        rows.append(result)
        if band in ("HIGH", "CRITICAL"):
            alerts.append({
                "account_id": row.account_id,
                "as_of": latest_as_of.isoformat(),
                "risk_score": int(final_score),
                "risk_band": band,
                "action": action,
            })

    results_df = pd.DataFrame([r.model_dump() for r in rows])
    alerts_df = pd.DataFrame(alerts)
    return results_df, alerts_df


def run_full_pipeline(
    accounts_path="data/raw/accounts.csv",
    transactions_path="data/raw/transactions.csv",
    artifact_dir="bank_ai/artifacts",
    results_dir="bank_ai/results",
    evaluate=True,
    score=True,
):
    cfg = load_config()
    txns, accounts, labels = load_and_validate(accounts_path, transactions_path)
    artifact_path = Path(artifact_dir)
    trained, test_df = _run_training(txns, accounts, labels, cfg, artifact_path)

    if evaluate:
        report_md, _ = _run_evaluation(trained, test_df, cfg)
        (artifact_path / "evaluation_report.md").write_text(report_md, encoding="utf-8")
        print("Evaluation report ->", artifact_path / "evaluation_report.md")

    if score:
        results_df, alerts_df = _score_latest_snapshot(txns, accounts, cfg, trained)
        out_path = Path(results_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        results_df["reason_codes"] = results_df["reason_codes"].apply(_json.dumps)
        results_df.to_csv(out_path / "bank_ai_results.csv", index=False)
        alerts_df.to_csv(out_path / "bank_alerts.csv", index=False)
        print("Results ->", out_path / "bank_ai_results.csv")
        print("Alerts  ->", out_path / "bank_alerts.csv")
        return results_df, alerts_df
    return None, None


if __name__ == "__main__":
    run_full_pipeline()
