"""Graph Construction Engine (MultiDiGraph) for Central AI.

Builds a directed NetworkX multigraph where:
- Nodes (V) are bank accounts enriched with Bank AI risk scores,
  alert flags, KYC tenure, and degree statistics.
- Directed Edges (E) are individual timestamped transactions
  (u -> v, key=tx_id) storing amount, UTC epoch, channel, and metadata.

MultiDiGraph is mandatory because mule layering frequently involves
rapid-fire split transfers (smurfing) between the same account pair.
"""

from typing import Iterable, Dict
import networkx as nx

from central_ai.schemas import AccountAlertRecord, TransactionRecord


class SingleBankGraphBuilder:
    """Constructs a directed multigraph from accounts and transactions."""

    def __init__(self, default_unalerted_score: float = 0.05) -> None:
        self.default_unalerted_score = default_unalerted_score

    def build_graph(
        self,
        accounts: Iterable[AccountAlertRecord],
        transactions: Iterable[TransactionRecord],
    ) -> nx.MultiDiGraph:
        """Build the graph. Nodes are accounts, edges are observed transfers."""
        graph = nx.MultiDiGraph()

        account_map: Dict[str, AccountAlertRecord] = {
            acc.account_id: acc for acc in accounts
        }

        # 1. Add explicit account nodes
        for acc_id, acc in account_map.items():
            graph.add_node(
                acc_id,
                bank_ai_score=acc.bank_ai_score,
                is_alerted=acc.is_alerted,
                alert_reasons=list(acc.alert_reasons),
                customer_segment=acc.customer_segment,
                account_age_days=acc.account_age_days,
            )

        # 2. Add transaction edges (sorted chronologically)
        sorted_txs = sorted(transactions, key=lambda tx: tx.timestamp)
        for tx in sorted_txs:
            for endpoint in (tx.source_account, tx.target_account):
                if not graph.has_node(endpoint):
                    graph.add_node(
                        endpoint,
                        bank_ai_score=self.default_unalerted_score,
                        is_alerted=False,
                        alert_reasons=[],
                        customer_segment="UNKNOWN",
                        account_age_days=365,
                    )

            graph.add_edge(
                tx.source_account,
                tx.target_account,
                key=tx.tx_id,
                tx_id=tx.tx_id,
                amount=tx.amount,
                timestamp=tx.timestamp,
                epoch_seconds=tx.timestamp.timestamp(),
                currency=tx.currency,
                channel=tx.channel,
                evidence_type="OBSERVED_LEDGER_FACT",
            )

        # 3. Compute node degree statistics
        for node in graph.nodes():
            graph.nodes[node]["in_degree"] = graph.in_degree(node)
            graph.nodes[node]["out_degree"] = graph.out_degree(node)

        return graph
