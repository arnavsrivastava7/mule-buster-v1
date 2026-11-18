"""Feature extraction, conservation analysis, and 0-100 risk scoring for Central AI.

Computes temporal velocity, amount conservation, chain depth, and Level 1
Bank AI fusion features.  Applies the guardrail multiplier and assigns
risk bands.  Generates human-readable explanation codes and the mandatory
fungibility caveat.
"""

import math
from typing import List
import networkx as nx

from central_ai.schemas import CandidateChainRecord, ComponentScores
from central_ai.chain_detection import RawTemporalPath


class ChainRiskScoringEngine:
    """Evaluate discovered paths and produce explainable 0-100 chain risk scores."""

    def __init__(
        self,
        weight_bank_ai: float = 0.35,
        weight_conservation: float = 0.25,
        weight_velocity: float = 0.20,
        weight_length: float = 0.20,
        velocity_half_life_minutes: float = 60.0,
        conservation_tolerance: float = 0.25,
    ) -> None:
        total = weight_bank_ai + weight_conservation + weight_velocity + weight_length
        if not math.isclose(total, 1.0, rel_tol=1e-4):
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")
        self.w_bank = weight_bank_ai
        self.w_cons = weight_conservation
        self.w_vel = weight_velocity
        self.w_len = weight_length
        self.tau = velocity_half_life_minutes
        self.epsilon = conservation_tolerance

    def evaluate_path(
        self,
        chain_index: int,
        raw_path: RawTemporalPath,
        graph: nx.MultiDiGraph,
    ) -> CandidateChainRecord:
        hops = raw_path.hops
        accounts = raw_path.accounts_path
        m = len(hops)

        # ── Temporal features ──
        duration_min = max(0.0, (hops[-1].epoch_seconds - hops[0].epoch_seconds) / 60.0)
        dwells = [
            max(0.0, (hops[i + 1].epoch_seconds - hops[i].epoch_seconds) / 60.0)
            for i in range(m - 1)
        ]
        mean_dwell = sum(dwells) / len(dwells) if dwells else 0.0
        vel_score = math.exp(-mean_dwell / self.tau)

        # ── Amount conservation features ──
        initial = hops[0].amount
        terminal = hops[-1].amount
        net_retention = terminal / initial if initial > 0 else 0.0

        step_ratios: List[float] = []
        step_scores: List[float] = []
        for i in range(m - 1):
            ratio = hops[i + 1].amount / hops[i].amount
            step_ratios.append(round(ratio, 4))
            deviation = abs(1.0 - ratio)
            s = max(0.0, 1.0 - (deviation / self.epsilon))
            if ratio > 1.02:
                s *= 0.75
            step_scores.append(s)
        cons_score = sum(step_scores) / len(step_scores) if step_scores else 0.0

        # ── Chain depth ──
        len_score = min(1.0, (m - 1) / 4.0)

        # ── Bank AI fusion ──
        node_scores = [
            float(graph.nodes[a].get("bank_ai_score", 0.05)) for a in accounts
        ]
        alerted = [a for a in accounts if graph.nodes[a].get("is_alerted", False)]
        bank_score = 0.6 * max(node_scores) + 0.4 * (sum(node_scores) / len(node_scores))

        # ── Weighted combination ──
        raw = 100.0 * (
            self.w_bank * bank_score
            + self.w_cons * cons_score
            + self.w_vel * vel_score
            + self.w_len * len_score
        )

        # Guardrail: no alerted nodes AND low bank score -> cap at 49
        if not alerted and bank_score < 0.25:
            final = min(49.0, raw)
        else:
            final = max(0.0, min(100.0, raw))

        band = self._band(final)
        codes = self._explanation_codes(
            m, mean_dwell, net_retention, cons_score, alerted, max(node_scores)
        )

        intermediates = ", ".join(accounts[1:-1]) if len(accounts) > 2 else "none"
        caveat = (
            f"Transfers {', '.join(raw_path.transaction_ids)} show "
            f"{net_retention * 100:.1f}% end-to-end retention across {m} hops "
            f"within {duration_min:.1f} minutes. Matching amounts do NOT prove "
            f"the same funds passed through {intermediates} due to account "
            f"balance fungibility; this chain is an inferred flow hypothesis."
        )

        return CandidateChainRecord(
            chain_id=f"CHAIN_{chain_index:03d}",
            accounts_path=accounts,
            transaction_ids=raw_path.transaction_ids,
            hop_count=m,
            duration_minutes=round(duration_min, 2),
            mean_hop_dwell_minutes=round(mean_dwell, 2),
            initial_amount=round(initial, 2),
            terminal_amount=round(terminal, 2),
            net_retention_ratio=round(net_retention, 4),
            step_retention_ratios=step_ratios,
            component_scores=ComponentScores(
                bank_ai_subscore=round(bank_score, 4),
                conservation_subscore=round(cons_score, 4),
                velocity_subscore=round(vel_score, 4),
                length_subscore=round(len_score, 4),
            ),
            chain_risk_score=round(final, 2),
            risk_band=band,
            explanation_codes=codes,
            fungibility_caveat=caveat,
        )

    @staticmethod
    def _band(score: float) -> str:
        if score >= 80:
            return "CRITICAL"
        if score >= 60:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _explanation_codes(
        hops, dwell, retention, cons, alerted, peak
    ) -> List[str]:
        codes = [f"MULTI_HOP_LAYERING_DEPTH_{hops}"]
        if dwell <= 15:
            codes.append(f"RAPID_PASS_THROUGH_DWELL_{dwell:.1f}M")
        elif dwell <= 60:
            codes.append(f"SUB_HOUR_RELAY_DWELL_{dwell:.1f}M")
        if cons >= 0.80:
            codes.append(f"HIGH_AMOUNT_CONSERVATION_{retention * 100:.0f}%")
        elif cons >= 0.50:
            codes.append(f"MODERATE_AMOUNT_CONSERVATION_{retention * 100:.0f}%")
        if alerted:
            codes.append(f"CONTAINS_{len(alerted)}_BANK_AI_ALERTED_ACCOUNTS")
        if peak >= 0.80:
            codes.append(f"HIGH_LOCAL_ANOMALY_PEAK_{peak:.2f}")
        return codes
