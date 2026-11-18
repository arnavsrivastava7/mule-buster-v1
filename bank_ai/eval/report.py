"""Evaluation reports and benchmark comparison tables (Section 6).

Generates side-by-side comparison tables across models (Rules vs LogReg vs LightGBM vs Hybrid)
and feature ablation tables.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd
# Clean format without external dependency

from bank_ai.config import Config
from bank_ai.eval.metrics import calculate_comprehensive_metrics, merchant_fpr_at_threshold
from bank_ai.features.build import ML_FEATURES
from bank_ai.models.train import TrainedBankAIModels
from bank_ai.rules.baseline import score_rules
from bank_ai.scoring.blend import blend_scores
from bank_ai.scoring.merchant_guard import merchant_adjustment


def evaluate_all_models(
    test_df: pd.DataFrame,
    models: TrainedBankAIModels,
    cfg: Config,
) -> Dict[str, Any]:
    """Score test set with all models and compare performance side-by-side."""
    y_true = test_df["target"].values

    # 1. Rules Baseline (0-100)
    rule_scores = []
    for row in test_df.itertuples():
        r_score, _ = score_rules(row, cfg)
        rule_scores.append(r_score)
    rule_scores = np.array(rule_scores)

    # 2. Logistic Regression Baseline (0-100)
    logreg_probs = models.predict_logreg_proba(test_df)
    logreg_scores = np.round(logreg_probs * 100)

    # 3. LightGBM Primary (0-100)
    lgbm_probs = models.predict_lgbm_proba(test_df)
    lgbm_scores = np.round(lgbm_probs * 100)

    # 4. Hybrid (LightGBM + Rules - Merchant Adjustment)
    hybrid_scores = []
    for i, row in enumerate(test_df.itertuples()):
        r_score = rule_scores[i]
        ml_p = lgbm_probs[i]
        adj, _, _ = merchant_adjustment(row, cfg)
        _, final_score = blend_scores(ml_p, r_score, adj, cfg)
        hybrid_scores.append(final_score)
    hybrid_scores = np.array(hybrid_scores)

    # Evaluation results for each candidate
    models_dict = {
        "Rules Baseline": (rule_scores, 40.0),
        "Logistic Regression": (logreg_scores, 50.0),
        "LightGBM Primary": (lgbm_scores, 50.0),
        "Hybrid Model": (hybrid_scores, cfg.band_high),
    }

    results = {}
    for name, (scores, thresh) in models_dict.items():
        metrics = calculate_comprehensive_metrics(y_true, scores, threshold=thresh)
        # Add merchant FPR
        temp_df = test_df.copy()
        temp_df["_eval_score"] = scores
        m_fpr = merchant_fpr_at_threshold(temp_df, "_eval_score", threshold=thresh)
        metrics["merchant_fpr"] = m_fpr
        results[name] = metrics

    return results


def format_comparison_table(results: Dict[str, Dict[str, Any]]) -> str:
    """Format markdown comparison table suitable for presentation to hackathon judges."""
    header = "| Model Architecture | PR-AUC | ROC-AUC | Precision | Recall | F1-Score | Recall@1% | Recall@2% | Merch FPR |"
    sep = "|---|---|---|---|---|---|---|---|---|"
    lines = [header, sep]

    for name, m in results.items():
        m_fpr_str = f"{m.get('merchant_fpr', {}).get('overall_merchant_fpr', 0.0):.1%}"
        line = (
            f"| **{name}** | {m['pr_auc']:.3f} | {m['roc_auc']:.3f} | "
            f"{m['precision']:.3f} | {m['recall']:.3f} | {m['f1_score']:.3f} | "
            f"{m['recall_at_1pct']:.1%} | {m['recall_at_2pct']:.1%} | {m_fpr_str} |"
        )
        lines.append(line)

    return "\n".join(lines)


def format_confusion_matrix_text(cm_dict: Dict[str, int]) -> str:
    """Format a textual representation of the confusion matrix."""
    tn, fp = cm_dict["tn"], cm_dict["fp"]
    fn, tp = cm_dict["fn"], cm_dict["tp"]
    total = tn + fp + fn + tp
    return (
        f"               Actual Negative   Actual Positive\n"
        f"Pred Negative      {tn:<14}  {fn:<14}\n"
        f"Pred Positive      {fp:<14}  {tp:<14}\n"
        f"(Total Evaluated: {total})"
    )


def run_feature_ablation(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """Train LightGBM dropping one feature at a time to determine feature impact."""
    from lightgbm import LGBMClassifier
    from sklearn.metrics import average_precision_score

    y_train = train_df["target"].values
    y_test = test_df["target"].values

    base_lgbm = LGBMClassifier(
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=15,
        random_state=42,
        verbosity=-1,
    )
    base_lgbm.fit(train_df[list(ML_FEATURES)].fillna(0.0), y_train)
    base_pr_auc = average_precision_score(y_test, base_lgbm.predict_proba(test_df[list(ML_FEATURES)].fillna(0.0))[:, 1])

    rows = [{"feature": "ALL_FEATURES (Baseline)", "pr_auc": base_pr_auc, "delta_pr_auc": 0.0}]

    for feat in ML_FEATURES:
        remaining = [f for f in ML_FEATURES if f != feat]
        model = LGBMClassifier(
            n_estimators=100,
            learning_rate=0.05,
            num_leaves=15,
            random_state=42,
            verbosity=-1,
        )
        model.fit(train_df[remaining].fillna(0.0), y_train)
        score = average_precision_score(y_test, model.predict_proba(test_df[remaining].fillna(0.0))[:, 1])
        rows.append({
            "feature": f"Drop {feat}",
            "pr_auc": float(score),
            "delta_pr_auc": float(score - base_pr_auc),
        })

    ablation_df = pd.DataFrame(rows).sort_values("delta_pr_auc")
    return ablation_df
