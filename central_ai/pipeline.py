"""Central AI end-to-end pipeline.

Reads Bank AI outputs and raw transaction data, runs graph analysis
and chain detection, produces central_results.csv and investigation JSON.
"""

from pathlib import Path
from datetime import datetime, timezone
import json

import pandas as pd

from central_ai.central_ingestion import (
    load_bank_ai_results,
    load_transactions,
    validate_ingested_data,
)
from central_ai.final_assessment import MuleBusterCentralAI
from central_ai.chain_detection import TimeRespectingPathFinder
from central_ai.chain_scoring import ChainRiskScoringEngine
from central_ai.transaction_graph import SingleBankGraphBuilder


def run_central_pipeline(
    bank_ai_results_path: str = "bank_ai/results/bank_ai_results.csv",
    bank_alerts_path: str = "bank_ai/results/bank_alerts.csv",
    transactions_path: str = "data/raw/transactions.csv",
    output_dir: str = "central_ai/results",
    bank_id: str = "BANK_SIM_01",
    min_hops: int = 2,
    max_hops: int = 6,
    max_hop_dwell_minutes: float = 1440.0,
    min_step_retention: float = 0.50,
    max_step_retention: float = 1.05,
    require_alerted: bool = True,
):
    """Run the full Central AI pipeline."""

    print("=" * 60)
    print("  Mule Buster Central AI - Chain Detection Pipeline")
    print("=" * 60)

    # 1. Ingest Bank AI results
    print("\n[1/5] Loading Bank AI results and transactions...")
    accounts, _ = load_bank_ai_results(bank_ai_results_path, bank_alerts_path)
    acc_ids = {a.account_id for a in accounts}
    transactions = load_transactions(transactions_path, bank_account_ids=acc_ids)

    summary = validate_ingested_data(accounts, transactions)
    print(f"      Accounts:     {summary['total_accounts']}")
    print(f"      Transactions: {summary['total_transactions']}")
    print(f"      Alerted:      {summary['alerted_accounts']}")
    if summary["disconnected_accounts"] > 0:
        print(f"      Disconnected: {summary['disconnected_accounts']}")

    # 2. Build graph
    print("\n[2/5] Building transaction graph...")
    builder = SingleBankGraphBuilder()
    finder = TimeRespectingPathFinder(
        min_hops=min_hops,
        max_hops=max_hops,
        max_hop_dwell_minutes=max_hop_dwell_minutes,
        min_step_retention=min_step_retention,
        max_step_retention=max_step_retention,
        require_alerted_participant=require_alerted,
    )
    scorer = ChainRiskScoringEngine()

    central_ai = MuleBusterCentralAI(
        graph_builder=builder,
        path_finder=finder,
        scoring_engine=scorer,
    )

    # 3. Run investigation
    batch_id = f"BATCH_{datetime.now(timezone.utc).strftime('%Y_%m_%d_%H%M%S')}"
    print(f"\n[3/5] Running investigation (batch {batch_id})...")
    record = central_ai.run_investigation(
        bank_id=bank_id,
        batch_id=batch_id,
        accounts=accounts,
        transactions=transactions,
    )

    gs = record.graph_summary
    print(f"      Graph nodes:  {gs['total_nodes']}")
    print(f"      Graph edges:  {gs['total_observed_edges']}")
    print(f"      Chains found: {gs['candidate_chains_discovered']}")

    # 4. Save results
    print("\n[4/5] Saving results...")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 4a. central_results.csv - one row per chain
    chain_rows = []
    for chain in record.candidate_chains:
        chain_rows.append({
            "chain_id": chain.chain_id,
            "evidence_classification": chain.evidence_classification,
            "accounts_path": " -> ".join(chain.accounts_path),
            "transaction_ids": ", ".join(chain.transaction_ids),
            "hop_count": chain.hop_count,
            "duration_minutes": chain.duration_minutes,
            "mean_hop_dwell_minutes": chain.mean_hop_dwell_minutes,
            "initial_amount": chain.initial_amount,
            "terminal_amount": chain.terminal_amount,
            "net_retention_ratio": chain.net_retention_ratio,
            "bank_ai_subscore": chain.component_scores.bank_ai_subscore,
            "conservation_subscore": chain.component_scores.conservation_subscore,
            "velocity_subscore": chain.component_scores.velocity_subscore,
            "length_subscore": chain.component_scores.length_subscore,
            "chain_risk_score": chain.chain_risk_score,
            "risk_band": chain.risk_band,
            "explanation_codes": "; ".join(chain.explanation_codes),
            "fungibility_caveat": chain.fungibility_caveat,
        })

    results_df = pd.DataFrame(chain_rows)
    results_file = out / "central_results.csv"
    results_df.to_csv(results_file, index=False)
    print(f"      central_results.csv -> {results_file}")

    # 4b. Full investigation JSON
    investigation_file = out / "investigation_record.json"
    with open(investigation_file, "w", encoding="utf-8") as f:
        json.dump(record.to_dict(), f, indent=2, default=str)
    print(f"      investigation JSON   -> {investigation_file}")

    # 5. Summary
    print("\n[5/5] Investigation Summary")
    print(f"      Investigation ID: {record.investigation_id}")
    print(f"      Bank:            {record.bank_id}")
    if record.candidate_chains:
        top = record.candidate_chains[0]
        print(f"      Top chain:       {top.chain_id} (score {top.chain_risk_score}, {top.risk_band})")
        print(f"      Path:            {' -> '.join(top.accounts_path)}")
        print(f"      Duration:        {top.duration_minutes} min, {top.hop_count} hops")
        print(f"      Retention:       {top.net_retention_ratio:.2%}")
        for code in top.explanation_codes:
            print(f"        - {code}")
    else:
        print("      No candidate chains discovered.")

    print("\n" + "=" * 60)
    print("  Pipeline complete.")
    print("=" * 60)

    return record


if __name__ == "__main__":
    run_central_pipeline()
