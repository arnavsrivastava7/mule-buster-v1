"""Ingestion & Validation Layer for Central AI.

Reads Bank AI results (bank_ai_results.csv, bank_alerts.csv) and raw
transaction data.  Enforces schema integrity, deduplicates events,
validates timestamps, and produces typed AccountAlertRecord and
TransactionRecord objects sorted chronologically.
"""

from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import json

import pandas as pd

from central_ai.schemas import (
    AccountAlertRecord,
    TransactionRecord,
    parse_iso_timestamp,
)


class IngestionError(Exception):
    """Raised when input data fails validation."""


def _normalise_score(raw_score: float) -> float:
    """Clamp a 0-100 integer score to the 0.0-1.0 range."""
    return max(0.0, min(1.0, raw_score / 100.0))


def load_bank_ai_results(
    results_path: str,
    alerts_path: Optional[str] = None,
) -> Tuple[List[AccountAlertRecord], Dict[str, Dict[str, Any]]]:
    """Parse bank_ai_results.csv into AccountAlertRecord objects.

    Returns (accounts, raw_features_by_id).
    """
    df = pd.read_csv(results_path)

    required = {"account_id", "risk_score", "risk_band"}
    missing = required - set(df.columns)
    if missing:
        raise IngestionError(f"Bank AI results missing columns: {missing}")

    # Deduplicate by account_id (keep highest risk_score)
    df = df.sort_values("risk_score", ascending=False).drop_duplicates(
        subset="account_id", keep="first"
    )

    # Load alerts file if provided (for alert_reasons)
    alert_set: Dict[str, List[str]] = {}
    if alerts_path and Path(alerts_path).exists():
        alerts_df = pd.read_csv(alerts_path)
        for row in alerts_df.itertuples():
            acc_id = str(row.account_id)
            alert_set.setdefault(acc_id, []).append(
                getattr(row, "action", "FLAGGED")
            )

    accounts: List[AccountAlertRecord] = []
    raw_features: Dict[str, Dict] = {}
    for row in df.itertuples():
        acc_id = str(row.account_id)
        score_0_1 = _normalise_score(float(row.risk_score))
        is_alerted = str(getattr(row, "risk_band", "LOW")) in ("HIGH", "CRITICAL")

        reasons = tuple(alert_set.get(acc_id, []))
        if is_alerted and not reasons:
            band = str(getattr(row, "risk_band", ""))
            reasons = (f"BANK_AI_{band}",)

        # Parse features if they exist
        feat_str = getattr(row, "features", None)
        if feat_str and isinstance(feat_str, str):
            try:
                raw_features[acc_id] = json.loads(feat_str.replace("'", '"'))
            except (json.JSONDecodeError, ValueError):
                raw_features[acc_id] = {}

        accounts.append(
            AccountAlertRecord(
                account_id=acc_id,
                bank_ai_score=score_0_1,
                is_alerted=is_alerted,
                alert_reasons=reasons,
                customer_segment="RETAIL",
                account_age_days=365,
            )
        )

    return accounts, raw_features


def load_transactions(
    transactions_path: str,
    bank_account_ids: Optional[set] = None,
) -> List[TransactionRecord]:
    """Parse raw transactions CSV into TransactionRecord objects.

    Handles two formats:
    1. Pairwise (sender_id, receiver_id, timestamp, amount)
    2. Ledger (account_id, direction, counterparty_id, ts, amount)

    Returns a chronologically sorted list with duplicates removed.
    """
    df = pd.read_csv(transactions_path)

    if df.empty:
        raise IngestionError("Transactions file is empty.")

    records: List[TransactionRecord] = []
    seen_ids: set = set()

    # Format 1: Pairwise ledger (from data_generator)
    if "sender_id" in df.columns and "receiver_id" in df.columns:
        time_col = "timestamp" if "timestamp" in df.columns else "ts"
        id_col = "transaction_id" if "transaction_id" in df.columns else "tx_id"

        channel_map = {
            "SALARY_NEFT": "NEFT", "NEFT": "NEFT", "RTGS": "RTGS",
            "IMPS": "IMPS", "UPI": "UPI", "TRANSFER": "IMPS",
            "ATM_WITHDRAWAL": "CASH", "CASH_DEPOSIT": "CASH",
            "CARD_PURCHASE": "CARD", "WALLET_TOPUP": "WALLET",
        }

        for row in df.itertuples(index=False):
            tx_id = str(getattr(row, id_col))
            if tx_id in seen_ids:
                continue
            seen_ids.add(tx_id)

            sender = str(row.sender_id)
            receiver = str(row.receiver_id)

            # Skip self-loops
            if sender == receiver:
                continue
            skip_names = {"EXTERNAL", "ATM_EXT", "CASH", "NONE", ""}
            if sender in skip_names or receiver in skip_names:
                continue
            if bank_account_ids and sender not in bank_account_ids and receiver not in bank_account_ids:
                continue

            ts_str = str(getattr(row, time_col))
            try:
                ts = parse_iso_timestamp(ts_str)
            except (ValueError, TypeError):
                continue

            tx_type = str(getattr(row, "transaction_type", "IMPS"))
            channel = channel_map.get(tx_type, "IMPS")

            try:
                records.append(TransactionRecord(
                    tx_id=tx_id,
                    source_account=sender,
                    target_account=receiver,
                    amount=float(row.amount),
                    timestamp=ts,
                    channel=channel,
                ))
            except ValueError:
                continue

    # Format 2: Ledger format (account_id, direction, counterparty_id)
    elif "direction" in df.columns and "account_id" in df.columns:
        time_col = "ts" if "ts" in df.columns else "timestamp"
        id_col = "txn_id" if "txn_id" in df.columns else "tx_id"

        for row in df.itertuples(index=False):
            direction = str(row.direction)
            if direction != "OUT":
                continue  # only emit one record per transfer
            tx_id = str(getattr(row, id_col))
            if tx_id in seen_ids:
                continue
            seen_ids.add(tx_id)

            sender = str(row.account_id)
            receiver = str(row.counterparty_id)
            if sender == receiver:
                continue

            ts_str = str(getattr(row, time_col))
            try:
                ts = parse_iso_timestamp(ts_str)
            except (ValueError, TypeError):
                continue

            channel = str(getattr(row, "channel", "IMPS"))
            try:
                records.append(TransactionRecord(
                    tx_id=tx_id,
                    source_account=sender,
                    target_account=receiver,
                    amount=float(row.amount),
                    timestamp=ts,
                    channel=channel,
                ))
            except ValueError:
                continue
    else:
        raise IngestionError(
            "Unrecognised transaction format. Need sender_id/receiver_id or "
            "account_id/direction/counterparty_id columns."
        )

    # Chronological sort
    records.sort(key=lambda r: r.timestamp)
    return records


def validate_ingested_data(
    accounts: List[AccountAlertRecord],
    transactions: List[TransactionRecord],
) -> Dict[str, Any]:
    """Run consistency checks and return a summary report."""
    acc_ids = {a.account_id for a in accounts}
    tx_acc_ids = set()
    for tx in transactions:
        tx_acc_ids.add(tx.source_account)
        tx_acc_ids.add(tx.target_account)

    disconnected = tx_acc_ids - acc_ids
    alerted = [a for a in accounts if a.is_alerted]

    return {
        "total_accounts": len(accounts),
        "total_transactions": len(transactions),
        "alerted_accounts": len(alerted),
        "disconnected_accounts": len(disconnected),
        "disconnected_ids": list(disconnected)[:10],
    }
