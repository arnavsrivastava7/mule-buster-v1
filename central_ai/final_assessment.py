"""Final assessment orchestrator for Central AI.

Combines ingestion, graph construction, chain detection, and scoring
into the complete InvestigationRecord output with observed transfers
and candidate chains cleanly separated.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any

from central_ai.schemas import (
    AccountAlertRecord,
    TransactionRecord,
    ObservedTransferSummary,
    InvestigationRecord,
)
from central_ai.transaction_graph import SingleBankGraphBuilder
from central_ai.chain_detection import TimeRespectingPathFinder
from central_ai.chain_scoring import ChainRiskScoringEngine


EPISTEMIC_DISCLAIMER = (
    "DISTINCTION OF EVIDENCE: 'observed_transfers' represent verified "
    "single-hop ledger transactions between specific account pairs within "
    "the bank. 'candidate_chains' represent inferred, time-respecting "
    "multi-hop flow hypotheses. Approximate amount conservation across "
    "sequential hops does NOT prove that identical underlying funds moved "
    "through the chain due to account balance fungibility."
)


class MuleBusterCentralAI:
    """Level 2 Central AI Coordinator for a single simulated bank."""

    def __init__(
        self,
        graph_builder: SingleBankGraphBuilder | None = None,
        path_finder: TimeRespectingPathFinder | None = None,
        scoring_engine: ChainRiskScoringEngine | None = None,
    ) -> None:
        self.graph_builder = graph_builder or SingleBankGraphBuilder()
        self.path_finder = path_finder or TimeRespectingPathFinder()
        self.scoring_engine = scoring_engine or ChainRiskScoringEngine()

    def run_investigation(
        self,
        bank_id: str,
        batch_id: str,
        accounts: List[AccountAlertRecord],
        transactions: List[TransactionRecord],
    ) -> InvestigationRecord:
        """Full Central AI workflow -> InvestigationRecord."""

        # 1. Build directed MultiDiGraph
        graph = self.graph_builder.build_graph(accounts, transactions)

        # 2. Discover time-respecting candidate paths
        raw_paths = self.path_finder.find_candidate_paths(graph)

        # 3. Score each chain
        chains = [
            self.scoring_engine.evaluate_path(i + 1, p, graph)
            for i, p in enumerate(raw_paths)
        ]
        chains.sort(key=lambda c: c.chain_risk_score, reverse=True)
        for rank, chain in enumerate(chains, 1):
            chain.chain_id = f"CHAIN_{rank:03d}"

        # 4. Catalog observed transfers
        sorted_txs = sorted(transactions, key=lambda t: t.timestamp)
        observed = [
            ObservedTransferSummary(
                tx_id=tx.tx_id,
                from_account=tx.source_account,
                to_account=tx.target_account,
                amount=tx.amount,
                timestamp=tx.timestamp.isoformat(),
                channel=tx.channel,
            )
            for tx in sorted_txs
        ]

        alerted_count = sum(
            1 for _, d in graph.nodes(data=True) if d.get("is_alerted", False)
        )

        summary: Dict[str, Any] = {
            "total_nodes": graph.number_of_nodes(),
            "total_observed_edges": graph.number_of_edges(),
            "alerted_accounts_count": alerted_count,
            "candidate_chains_discovered": len(chains),
            "highest_chain_risk_score": chains[0].chain_risk_score if chains else 0.0,
        }

        return InvestigationRecord(
            investigation_id=f"INV-{batch_id}",
            bank_id=bank_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            graph_summary=summary,
            epistemic_disclaimer=EPISTEMIC_DISCLAIMER,
            observed_transfers=observed,
            candidate_chains=chains,
        )
