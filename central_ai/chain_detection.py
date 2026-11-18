"""Time-Respecting Path Discovery Engine for Central AI.

Performs constrained DFS where every hop e_i -> e_{i+1} must satisfy:
1. Causal Monotonicity: t(e_{i+1}) >= t(e_i)
2. Hop Dwell Window: 0 <= t(e_{i+1}) - t(e_i) <= max_hop_dwell
3. Simple Path Constraint: no repeated vertices
4. Plausible Flow Ratio: a(e_{i+1})/a(e_i) in [rho_min, rho_max]
"""

from dataclasses import dataclass
from typing import List, Set
import networkx as nx


@dataclass(frozen=True)
class EdgeHop:
    """One directed transaction hop along a path."""

    tx_id: str
    source: str
    target: str
    amount: float
    epoch_seconds: float
    channel: str


@dataclass
class RawTemporalPath:
    """Sequence of time-respecting EdgeHops discovered in the graph."""

    hops: List[EdgeHop]

    @property
    def accounts_path(self) -> List[str]:
        if not self.hops:
            return []
        return [self.hops[0].source] + [h.target for h in self.hops]

    @property
    def transaction_ids(self) -> List[str]:
        return [h.tx_id for h in self.hops]


class TimeRespectingPathFinder:
    """Extract time-respecting simple paths from a NetworkX MultiDiGraph.

    A path (e_1, e_2, ..., e_m) is valid iff for each consecutive pair:
      - t(e_{i+1}) >= t(e_i)           (causal ordering)
      - delta <= max_hop_dwell         (within dwell window)
      - min_retention <= ratio <= max_retention  (plausible amount)
      - no vertex is visited twice     (simple path)
    """

    def __init__(
        self,
        min_hops: int = 2,
        max_hops: int = 6,
        max_hop_dwell_minutes: float = 1440.0,  # 24 hours
        min_step_retention: float = 0.50,
        max_step_retention: float = 1.05,
        require_alerted_participant: bool = True,
    ) -> None:
        if min_hops < 2:
            raise ValueError("min_hops must be >= 2 to form a chain.")
        self.min_hops = min_hops
        self.max_hops = max_hops
        self.max_hop_dwell_seconds = max_hop_dwell_minutes * 60.0
        self.min_step_retention = min_step_retention
        self.max_step_retention = max_step_retention
        self.require_alerted_participant = require_alerted_participant

    def find_candidate_paths(
        self, graph: nx.MultiDiGraph
    ) -> List[RawTemporalPath]:
        """Find maximal time-respecting paths, deduplicating sub-paths."""
        all_paths: List[RawTemporalPath] = []

        # Collect all edges sorted chronologically
        initial_edges: List[EdgeHop] = []
        for u, v, key, data in graph.edges(keys=True, data=True):
            initial_edges.append(
                EdgeHop(
                    tx_id=str(key),
                    source=u,
                    target=v,
                    amount=float(data["amount"]),
                    epoch_seconds=float(data["epoch_seconds"]),
                    channel=str(data.get("channel", "IMPS")),
                )
            )
        initial_edges.sort(key=lambda e: e.epoch_seconds)

        for first_hop in initial_edges:
            visited: Set[str] = {first_hop.source, first_hop.target}
            self._dfs_extend(graph, [first_hop], visited, all_paths)

        # Filter: require at least one alerted account
        if self.require_alerted_participant:
            all_paths = [
                p for p in all_paths
                if any(
                    graph.nodes[acc].get("is_alerted", False)
                    for acc in p.accounts_path
                )
            ]

        return self._prune_subpaths(all_paths)

    def _dfs_extend(
        self,
        graph: nx.MultiDiGraph,
        current_hops: List[EdgeHop],
        visited: Set[str],
        collected: List[RawTemporalPath],
    ) -> None:
        last = current_hops[-1]
        node = last.target
        extended = False

        if len(current_hops) < self.max_hops and graph.has_node(node):
            for _, nxt, key, data in graph.out_edges(node, keys=True, data=True):
                if nxt in visited:
                    continue

                epoch = float(data["epoch_seconds"])
                delta = epoch - last.epoch_seconds

                # Causal monotonicity + dwell window
                if delta < 0.0 or delta > self.max_hop_dwell_seconds:
                    continue

                # Plausible amount retention
                ratio = float(data["amount"]) / last.amount
                if not (self.min_step_retention <= ratio <= self.max_step_retention):
                    continue

                hop = EdgeHop(
                    tx_id=str(key),
                    source=node,
                    target=nxt,
                    amount=float(data["amount"]),
                    epoch_seconds=epoch,
                    channel=str(data.get("channel", "IMPS")),
                )

                visited.add(nxt)
                current_hops.append(hop)
                extended = True
                self._dfs_extend(graph, current_hops, visited, collected)
                current_hops.pop()
                visited.remove(nxt)

        # Record path if it meets minimum hops
        if len(current_hops) >= self.min_hops and not extended:
            collected.append(RawTemporalPath(hops=list(current_hops)))

    @staticmethod
    def _prune_subpaths(paths: List[RawTemporalPath]) -> List[RawTemporalPath]:
        """Remove paths whose tx_id sequence is a contiguous sub-sequence of a longer path."""
        sorted_paths = sorted(paths, key=lambda p: len(p.hops), reverse=True)
        kept: List[RawTemporalPath] = []
        kept_tuples: List[tuple] = []

        for cand in sorted_paths:
            ct = tuple(cand.transaction_ids)
            is_sub = False
            for existing in kept_tuples:
                if len(ct) <= len(existing):
                    for i in range(len(existing) - len(ct) + 1):
                        if existing[i : i + len(ct)] == ct:
                            is_sub = True
                            break
                if is_sub:
                    break
            if not is_sub:
                kept.append(cand)
                kept_tuples.append(ct)
        return kept
