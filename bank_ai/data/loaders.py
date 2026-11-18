"""Data loaders and schema adapters for Bank AI.

Loads transactions.csv and accounts.csv, verifies schemas, and prepares
the single-bank ledger format used for snapshot-based feature engineering.
"""

from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import pandas as pd

from bank_ai.schemas import (
    validate_transactions,
    validate_accounts,
    assert_features_exclude_labels,
)


def adapt_raw_transactions(raw_txns: pd.DataFrame, bank_account_ids: Optional[set] = None) -> pd.DataFrame:
    """Adapt transactions to the single-bank ledger schema.

    If transactions already have (txn_id, ts, account_id, direction, amount, counterparty_id, ...),
    it validates and returns them.
    If transactions have (transaction_id, sender_id, receiver_id, amount, timestamp, ...),
    it explodes each transfer into dual ledger entries (OUT for sender, IN for receiver).
    """
    df = raw_txns.copy()

    # Case 1: Already in single-bank ledger format
    if "direction" in df.columns and "account_id" in df.columns:
        if "txn_id" not in df.columns and "transaction_id" in df.columns:
            df["txn_id"] = df["transaction_id"]
        if "ts" not in df.columns and "timestamp" in df.columns:
            df["ts"] = df["timestamp"]
        if "counterparty_is_internal" not in df.columns:
            df["counterparty_is_internal"] = True
        if "channel" not in df.columns:
            df["channel"] = "TRANSFER"
        return validate_transactions(df)

    # Case 2: Pairwise ledger (sender_id, receiver_id, timestamp, amount, transaction_type)
    if "sender_id" not in df.columns or "receiver_id" not in df.columns:
        raise ValueError(
            f"Transactions must have either direction/account_id or sender_id/receiver_id. Found: {list(df.columns)}"
        )

    time_col = "timestamp" if "timestamp" in df.columns else "ts"
    txn_id_col = "transaction_id" if "transaction_id" in df.columns else "txn_id"
    type_col = "transaction_type" if "transaction_type" in df.columns else "channel"

    channel_map = {
        "SALARY_NEFT": "TRANSFER",
        "NEFT": "TRANSFER",
        "RTGS": "TRANSFER",
        "IMPS": "TRANSFER",
        "UPI": "TRANSFER",
        "TRANSFER": "TRANSFER",
        "ATM_WITHDRAWAL": "CASH",
        "CASH_DEPOSIT": "CASH",
        "CARD_PURCHASE": "CARD",
        "WALLET_TOPUP": "WALLET",
    }

    entries = []
    if bank_account_ids is None:
        bank_account_ids = set(df["sender_id"]).union(set(df["receiver_id"]))

    for row in df.itertuples(index=False):
        raw_id = str(getattr(row, txn_id_col))
        ts = str(getattr(row, time_col))
        amt = float(getattr(row, "amount"))
        sender = str(getattr(row, "sender_id"))
        receiver = str(getattr(row, "receiver_id"))
        tx_type = str(getattr(row, type_col, "TRANSFER"))
        channel = channel_map.get(tx_type, "TRANSFER")

        # Sender OUT entry (if sender belongs to this bank)
        if sender in bank_account_ids and sender not in ("EXTERNAL_PAYER", "ATM_EXT", "CASH", "NONE", "EXTERNAL"):
            is_internal = receiver in bank_account_ids
            entries.append({
                "txn_id": f"{raw_id}_OUT",
                "ts": ts,
                "account_id": sender,
                "direction": "OUT",
                "amount": amt,
                "counterparty_id": receiver,
                "counterparty_is_internal": is_internal,
                "channel": channel,
            })

        # Receiver IN entry (if receiver belongs to this bank)
        if receiver in bank_account_ids and receiver not in ("EXTERNAL_PAYEE", "ATM_EXT", "CASH", "NONE", "EXTERNAL"):
            is_internal = sender in bank_account_ids
            entries.append({
                "txn_id": f"{raw_id}_IN",
                "ts": ts,
                "account_id": receiver,
                "direction": "IN",
                "amount": amt,
                "counterparty_id": sender,
                "counterparty_is_internal": is_internal,
                "channel": channel,
            })

    ledger_df = pd.DataFrame(entries)
    if ledger_df.empty:
        raise ValueError("No valid ledger entries could be extracted from transactions.")
    return validate_transactions(ledger_df)


def adapt_raw_accounts(raw_accounts: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Adapt raw accounts into clean accounts schema and separate labels DataFrame.

    Returns:
        (accounts_df, labels_df)
    """
    df = raw_accounts.copy()

    # Open date mapping
    date_col = "opened_on" if "opened_on" in df.columns else ("open_date" if "open_date" in df.columns else None)
    if date_col:
        df["open_date"] = pd.to_datetime(df[date_col]).dt.date
    else:
        df["open_date"] = pd.to_datetime("2025-01-01").date()

    # Customer type & merchant mapping
    role_col = "account_role" if "account_role" in df.columns else "customer_type"
    if "is_registered_merchant" not in df.columns:
        if "account_role" in df.columns:
            df["is_registered_merchant"] = df["account_role"].astype(str).str.contains("MERCHANT|SHOP|STORE", case=False)
        else:
            df["is_registered_merchant"] = False
    else:
        df["is_registered_merchant"] = df["is_registered_merchant"].astype(bool)

    if "customer_type" not in df.columns or df["customer_type"].isna().any():
        if "account_role" in df.columns:
            df["customer_type"] = np.where(
                df["account_role"].astype(str).str.contains("BUSINESS|MERCHANT|EMPLOYER|PAYROLL", case=False),
                "BUSINESS",
                "INDIVIDUAL",
            )
        else:
            df["customer_type"] = "INDIVIDUAL"

    if "merchant_category" not in df.columns:
        df["merchant_category"] = np.where(df["is_registered_merchant"], "RETAIL", None)

    # Clean accounts DataFrame
    accounts_clean = df[[
        "account_id",
        "open_date",
        "customer_type",
        "is_registered_merchant",
        "merchant_category",
    ]].copy()
    accounts_clean = validate_accounts(accounts_clean)

    # Separate ground truth labels table
    label_col = "ground_truth_label" if "ground_truth_label" in df.columns else ("label" if "label" in df.columns else None)
    if label_col:
        is_mule = df[label_col].astype(str).str.startswith("1_MULE")
        archetype = df[label_col].astype(str)
    else:
        is_mule = pd.Series(False, index=df.index)
        archetype = pd.Series("LEGITIMATE", index=df.index)

    labels_df = pd.DataFrame({
        "account_id": df["account_id"],
        "is_mule": is_mule,
        "mule_start_ts": None,
        "mule_end_ts": None,
        "archetype": archetype,
    })

    return accounts_clean, labels_df


def load_and_validate(accounts_path: str, transactions_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load raw CSV files and validate them against Bank AI schemas.

    Returns:
        (ledger_transactions, accounts, ground_truth_labels)
    """
    raw_acc = pd.read_csv(accounts_path)
    raw_tx = pd.read_csv(transactions_path)

    accounts_df, labels_df = adapt_raw_accounts(raw_acc)
    bank_ids = set(accounts_df["account_id"])
    txns_df = adapt_raw_transactions(raw_tx, bank_account_ids=bank_ids)

    return txns_df, accounts_df, labels_df
