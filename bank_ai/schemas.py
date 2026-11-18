"""Table checks and the scored-account output model.

Ground-truth columns are defined here so they stay out of the feature list.
"""

from datetime import datetime
from typing import Literal, Optional

import pandas as pd
import pandera.pandas as pa
from pydantic import BaseModel, Field

TRANSACTION_COLUMNS = (
    "txn_id",
    "ts",
    "account_id",
    "direction",
    "amount",
    "counterparty_id",
    "counterparty_is_internal",
    "channel",
)

ACCOUNT_COLUMNS = (
    "account_id",
    "open_date",
    "customer_type",
    "is_registered_merchant",
    "merchant_category",
)

LABEL_COLUMNS = (
    "account_id",
    "is_mule",
    "mule_start_ts",
    "mule_end_ts",
    "archetype",
)

# Never pass these to a model. They are answers, not behavior.
FORBIDDEN_FEATURE_COLUMNS = frozenset(
    {
        "is_mule",
        "mule_start_ts",
        "mule_end_ts",
        "archetype",
        "ground_truth_label",
        "label",
        "predicted_label",
    }
)

DIRECTIONS = ("IN", "OUT")
CHANNELS = ("TRANSFER", "CARD", "CASH", "WALLET", "OTHER")
CUSTOMER_TYPES = ("INDIVIDUAL", "BUSINESS")
FEEDBACK_DECISIONS = ("FALSE_POSITIVE", "CONFIRMED")

DISCLAIMER = (
    "A high risk score is a review flag for this simulation. It is not proof of fraud."
)


transactions_schema = pa.DataFrameSchema(
    {
        "txn_id": pa.Column(str, unique=True, nullable=False),
        "account_id": pa.Column(str, nullable=False),
        "direction": pa.Column(str, pa.Check.isin(DIRECTIONS), nullable=False),
        "amount": pa.Column(float, pa.Check.gt(0), nullable=False),
        "counterparty_id": pa.Column(str, nullable=False),
        "counterparty_is_internal": pa.Column(bool, nullable=False),
        "channel": pa.Column(str, pa.Check.isin(CHANNELS), nullable=False),
    },
    strict=False,
)


class ReasonCode(BaseModel):
    """One plain-language reason attached to a score."""

    code: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    feature: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    points: float
    message: str


class AccountRiskResult(BaseModel):
    """One scored account. schema_version stays 1.0 until the fields change."""

    schema_version: str = "1.0"
    run_id: str
    model_version: str
    account_id: str
    as_of: datetime
    risk_score: int = Field(ge=0, le=100)
    risk_band: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    rule_score: int = Field(ge=0, le=100)
    ml_score: int = Field(ge=0, le=100)
    merchant_adjustment: int = Field(ge=0, le=25)
    recommended_action: Literal["NONE", "MONITOR", "ANALYST_REVIEW", "PRIORITY_REVIEW"]
    reason_codes: list[ReasonCode]
    features: dict[str, float]
    flags: dict[str, bool]


def assert_features_exclude_labels(columns):
    """Stop training if an answer column slipped into the feature matrix."""
    overlap = FORBIDDEN_FEATURE_COLUMNS.intersection(columns)
    if overlap:
        names = ", ".join(sorted(overlap))
        raise ValueError(f"Ground-truth columns cannot be model inputs: {names}.")


def validate_transactions(frame):
    """Check the ledger schema, then Pandera's column rules."""
    missing = [column for column in TRANSACTION_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Transactions are missing columns: {missing}.")
    if frame[list(TRANSACTION_COLUMNS)].isna().any().any():
        raise ValueError("Transactions contain missing values.")
    if frame["txn_id"].duplicated().any():
        raise ValueError("Duplicate txn_id values are not allowed.")
    checked = frame.copy()
    checked["amount"] = checked["amount"].astype(float)
    checked["counterparty_is_internal"] = checked["counterparty_is_internal"].astype(bool)
    transactions_schema.validate(checked)
    timestamps = pd.to_datetime(frame["ts"], utc=True)
    if timestamps.isna().any():
        raise ValueError("Every transaction timestamp must be a real datetime.")
    return frame


def validate_accounts(frame):
    """Check the account table used at scoring time."""
    missing = [column for column in ACCOUNT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Accounts are missing columns: {missing}.")
    if frame["account_id"].duplicated().any():
        raise ValueError("Duplicate account_id values are not allowed.")
    if frame[list(ACCOUNT_COLUMNS)].isna().any().any() and frame["merchant_category"].isna().all():
        pass
    required = [column for column in ACCOUNT_COLUMNS if column != "merchant_category"]
    if frame[required].isna().any().any():
        raise ValueError("Accounts contain missing values outside merchant_category.")
    unknown = sorted(set(frame["customer_type"]) - set(CUSTOMER_TYPES))
    if unknown:
        raise ValueError(f"Unknown customer_type values: {unknown}.")
    return frame
