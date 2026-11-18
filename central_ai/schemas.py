"""Data contracts and epistemic separation structures for Central AI.

Ground rules:
- observed_transfers are verified ledger facts.
- candidate_chains are inferred temporal flow hypotheses.
- These two categories must NEVER be mixed or confused.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


def parse_iso_timestamp(ts_str: str) -> datetime:
    """Parse ISO-8601 string into a timezone-aware UTC datetime."""
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class AccountAlertRecord:
    """Level 1 Bank AI account metadata and local anomaly score."""

    account_id: str
    bank_ai_score: float          # normalised [0.0, 1.0]
    is_alerted: bool
    alert_reasons: tuple = ()     # frozen needs hashable
    customer_segment: str = "RETAIL"
    account_age_days: int = 365

    def __post_init__(self) -> None:
        if not (0.0 <= self.bank_ai_score <= 1.0):
            raise ValueError(
                f"bank_ai_score for {self.account_id} must be in [0.0, 1.0], "
                f"got {self.bank_ai_score}"
            )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AccountAlertRecord":
        return cls(
            account_id=str(d["account_id"]),
            bank_ai_score=float(d["bank_ai_score"]),
            is_alerted=bool(d["is_alerted"]),
            alert_reasons=tuple(d.get("alert_reasons", ())),
            customer_segment=str(d.get("customer_segment", "RETAIL")),
            account_age_days=int(d.get("account_age_days", 365)),
        )


@dataclass(frozen=True)
class TransactionRecord:
    """Observed single-bank ledger transfer (Hard Fact)."""

    tx_id: str
    source_account: str
    target_account: str
    amount: float
    timestamp: datetime
    currency: str = "INR"
    channel: str = "IMPS"

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError(
                f"Transaction {self.tx_id} amount must be positive, got {self.amount}"
            )
        if self.source_account == self.target_account:
            raise ValueError(
                f"Self-transfer not allowed in transaction {self.tx_id}"
            )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TransactionRecord":
        ts = d["timestamp"]
        if isinstance(ts, str):
            ts = parse_iso_timestamp(ts)
        return cls(
            tx_id=str(d["tx_id"]),
            source_account=str(d["source_account"]),
            target_account=str(d["target_account"]),
            amount=float(d["amount"]),
            timestamp=ts,
            currency=str(d.get("currency", "INR")),
            channel=str(d.get("channel", "IMPS")),
        )


@dataclass
class ComponentScores:
    """Normalised [0, 1] sub-scores that combine into the Chain Risk Score."""

    bank_ai_subscore: float
    conservation_subscore: float
    velocity_subscore: float
    length_subscore: float


@dataclass
class CandidateChainRecord:
    """Inferred temporal flow hypothesis (NOT a verified ledger fact)."""

    chain_id: str
    accounts_path: List[str]
    transaction_ids: List[str]
    hop_count: int
    duration_minutes: float
    mean_hop_dwell_minutes: float
    initial_amount: float
    terminal_amount: float
    net_retention_ratio: float
    step_retention_ratios: List[float]
    component_scores: ComponentScores
    chain_risk_score: float       # 0-100
    risk_band: str                # LOW / MEDIUM / HIGH / CRITICAL
    explanation_codes: List[str]
    fungibility_caveat: str
    evidence_classification: str = "INFERRED_TEMPORAL_FLOW_HYPOTHESIS"


@dataclass
class ObservedTransferSummary:
    """Verified ledger fact for the investigation dossier."""

    tx_id: str
    from_account: str
    to_account: str
    amount: float
    timestamp: str
    channel: str
    evidence_type: str = "OBSERVED_LEDGER_FACT"


@dataclass
class InvestigationRecord:
    """Final Central AI output artifact."""

    investigation_id: str
    bank_id: str
    generated_at: str
    graph_summary: Dict[str, Any]
    epistemic_disclaimer: str
    observed_transfers: List[ObservedTransferSummary]
    candidate_chains: List[CandidateChainRecord]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
