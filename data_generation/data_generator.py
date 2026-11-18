"""Build reproducible synthetic accounts and transactions for one bank.

Ground-truth labels stay in the column ground_truth_label. This module does
not create a prediction column. Model output belongs in a later file.

Run it from the project folder with the virtual environment turned on:

    python -m data_generation.data_generator
"""

import csv
import random
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pandas as pd

from data_generation.scenario_generator import (
    ACCOUNT_COUNT,
    BANK_PROFILES,
    CANONICAL_LEDGER,
    GROUND_TRUTH_LABELS,
    LABEL_LEGITIMATE_DECOY,
    LABEL_LEGITIMATE_NORMAL,
    MULE_LABELS,
    TIMEZONE_SUFFIX,
    TRANSACTION_COLUMNS,
    TRANSACTION_TYPES,
    account_role,
    bank_profile,
    scenario_for_number,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
IST = timezone(timedelta(hours=5, minutes=30))
OPENED_ON_ANCHOR = date(2026, 10, 1)
CITY_CODES = ("BLR", "HYD", "MUM", "DEL", "CHN", "PUN")
ACCOUNT_COLUMNS = (
    "account_id",
    "bank_id",
    "account_role",
    "ground_truth_label",
    "is_legitimate_decoy",
    "city_code",
    "opened_on",
    "opening_balance_inr",
)


def load_canonical_rows():
    """Read the specification ledger and check that every scenario owns its rows."""
    reader = csv.DictReader(StringIO(CANONICAL_LEDGER.strip()))
    if tuple(reader.fieldnames or ()) != TRANSACTION_COLUMNS:
        raise ValueError("The specification ledger header does not match the required columns.")

    rows = []
    for expected_number, row in enumerate(reader, start=1):
        transaction_number = int(row["transaction_id"].split("_")[1])
        if transaction_number != expected_number:
            raise ValueError(
                f"Expected TXN_{expected_number:04d}, found {row['transaction_id']}."
            )
        scenario_for_number(transaction_number)
        rows.append(row)

    covered = set()
    for scenario_row in rows:
        covered.add(int(scenario_row["transaction_id"].split("_")[1]))
    expected = set(range(1, len(rows) + 1))
    if covered != expected:
        raise ValueError("Scenario coverage does not match the ledger transaction numbers.")
    return rows


def format_account_id(profile, account_number):
    return f"{profile.account_prefix}_{account_number:03d}"


def format_transaction_id(profile, transaction_number):
    return f"{profile.transaction_prefix}_{transaction_number:04d}"


def shift_timestamp(timestamp_text, day_shift):
    """Keep the +05:30 offset and move the calendar date for another bank."""
    if not timestamp_text.endswith(TIMEZONE_SUFFIX):
        raise ValueError(f"Timestamp {timestamp_text} must use {TIMEZONE_SUFFIX}.")
    parsed = datetime.fromisoformat(timestamp_text)
    if parsed.utcoffset() != IST.utcoffset(None):
        raise ValueError(f"Timestamp {timestamp_text} is not +05:30.")
    shifted = parsed + timedelta(days=day_shift)
    return shifted.isoformat(timespec="seconds")


def account_number_from_id(account_id):
    return int(account_id.rsplit("_", 1)[1])


def build_transactions(profile):
    """Replay the specification for one bank."""
    replayed = []
    for row in load_canonical_rows():
        transaction_number = int(row["transaction_id"].split("_")[1])
        sender_number = account_number_from_id(row["sender_id"])
        receiver_number = account_number_from_id(row["receiver_id"])
        replayed.append(
            {
                "transaction_id": format_transaction_id(profile, transaction_number),
                "sender_id": format_account_id(profile, sender_number),
                "receiver_id": format_account_id(profile, receiver_number),
                "amount": row["amount"],
                "timestamp": shift_timestamp(row["timestamp"], profile.day_shift),
                "transaction_type": row["transaction_type"],
                "ground_truth_label": row["ground_truth_label"],
            }
        )
    return pd.DataFrame(replayed, columns=TRANSACTION_COLUMNS)


def _label_for_account(account_id, transactions):
    """Derive an account label from transaction ground truth, never from a model."""
    involved = transactions[
        (transactions["sender_id"] == account_id) | (transactions["receiver_id"] == account_id)
    ]
    mule_labels = involved.loc[
        involved["ground_truth_label"].isin(MULE_LABELS),
        "ground_truth_label",
    ]
    if not mule_labels.empty:
        counts = mule_labels.value_counts()
        top_count = counts.max()
        for label in MULE_LABELS:
            if counts.get(label, 0) == top_count:
                return label

    sent_decoy = (
        (transactions["sender_id"] == account_id)
        & (transactions["ground_truth_label"] == LABEL_LEGITIMATE_DECOY)
    ).any()
    decoy_touches = (involved["ground_truth_label"] == LABEL_LEGITIMATE_DECOY).sum()
    if sent_decoy or decoy_touches >= 3:
        return LABEL_LEGITIMATE_DECOY
    return LABEL_LEGITIMATE_NORMAL


def build_accounts(profile, transactions):
    """Create 100 simulated accounts. Profile fields use the bank's fixed seed."""
    rng = random.Random(profile.seed)
    accounts = []
    for number in range(1, ACCOUNT_COUNT + 1):
        account_id = format_account_id(profile, number)
        label = _label_for_account(account_id, transactions)
        days_before_window = rng.randint(120, 1400)
        opening_balance = rng.randint(5_000, 200_000)
        accounts.append(
            {
                "account_id": account_id,
                "bank_id": profile.bank_id,
                "account_role": account_role(number),
                "ground_truth_label": label,
                "is_legitimate_decoy": label == LABEL_LEGITIMATE_DECOY,
                "city_code": rng.choice(CITY_CODES),
                "opened_on": (OPENED_ON_ANCHOR - timedelta(days=days_before_window)).isoformat(),
                "opening_balance_inr": f"{opening_balance:.2f}",
            }
        )
    return pd.DataFrame(accounts, columns=ACCOUNT_COLUMNS)


def validate_tables(accounts, transactions):
    """Reject missing values, duplicate IDs, bad timestamps, and unknown labels."""
    problems = []

    if list(transactions.columns) != list(TRANSACTION_COLUMNS):
        problems.append("Transaction columns do not match the specification.")
    if "predicted_label" in transactions.columns or "prediction" in transactions.columns:
        problems.append("Ground truth must stay separate from model predictions.")
    if transactions.isna().any().any() or accounts.isna().any().any():
        problems.append("Missing values are not allowed.")
    if transactions.eq("").any().any() or accounts.eq("").any().any():
        problems.append("Blank values are not allowed.")

    duplicate_ids = transactions["transaction_id"].duplicated()
    if duplicate_ids.any():
        duplicated = transactions.loc[duplicate_ids, "transaction_id"].tolist()
        problems.append(f"Duplicate transaction IDs: {duplicated}.")
    if accounts["account_id"].duplicated().any():
        problems.append("Duplicate account IDs are not allowed.")

    known_accounts = set(accounts["account_id"])
    unknown_accounts = sorted(
        (set(transactions["sender_id"]) | set(transactions["receiver_id"])) - known_accounts
    )
    if unknown_accounts:
        problems.append(f"Transactions refer to unknown accounts: {unknown_accounts}.")

    timestamps = []
    for timestamp_text in transactions["timestamp"]:
        if not str(timestamp_text).endswith(TIMEZONE_SUFFIX):
            problems.append(f"Timestamp {timestamp_text} must use {TIMEZONE_SUFFIX}.")
            continue
        parsed = datetime.fromisoformat(str(timestamp_text))
        if parsed.utcoffset() != IST.utcoffset(None):
            problems.append(f"Timestamp {timestamp_text} is not +05:30.")
        timestamps.append(parsed)
    if timestamps != sorted(timestamps) or len(set(timestamps)) != len(timestamps):
        problems.append("Timestamps must be unique and in increasing order.")

    unknown_labels = sorted(set(transactions["ground_truth_label"]) - set(GROUND_TRUTH_LABELS))
    if unknown_labels:
        problems.append(f"Unknown ground-truth labels: {unknown_labels}.")
    unknown_types = sorted(set(transactions["transaction_type"]) - set(TRANSACTION_TYPES))
    if unknown_types:
        problems.append(f"Unknown transaction types: {unknown_types}.")

    for row in transactions.itertuples(index=False):
        amount = _parse_amount(row.amount)
        if amount <= 0:
            problems.append(f"{row.transaction_id} must have a positive amount.")
        same_account = row.sender_id == row.receiver_id
        if row.transaction_type == "ATM_WITHDRAWAL" and not same_account:
            problems.append(f"{row.transaction_id} cash withdrawal must use one account.")
        if row.transaction_type != "ATM_WITHDRAWAL" and same_account:
            problems.append(f"{row.transaction_id} must use two different accounts.")

    if problems:
        raise ValueError("Synthetic data failed validation:\n- " + "\n- ".join(problems))


def _parse_amount(amount):
    return round(float(amount), 2)


def summarize(profile, accounts, transactions):
    """Build the text report of accounts, transactions, and ground-truth labels."""
    label_counts = (
        transactions["ground_truth_label"].value_counts().reindex(GROUND_TRUTH_LABELS, fill_value=0)
    )
    decoy_accounts = int(accounts["is_legitimate_decoy"].sum())
    lines = [
        "Mule Buster synthetic data summary",
        f"Bank: {profile.bank_id}",
        f"Random seed: {profile.seed}",
        f"Accounts: {len(accounts)}",
        f"Transactions: {len(transactions)}",
        "Missing values: 0",
        "Duplicate transaction IDs: 0",
        f"First timestamp: {transactions['timestamp'].iloc[0]}",
        f"Last timestamp: {transactions['timestamp'].iloc[-1]}",
        f"Timezone: {TIMEZONE_SUFFIX}",
        f"Legitimate decoy accounts: {decoy_accounts}",
        "",
        "Ground-truth labels (these are scenario labels, not model predictions):",
    ]
    for label, count in label_counts.items():
        lines.append(f"  {label}: {int(count)}")
    lines.extend(
        [
            "",
            "Account ground-truth labels:",
        ]
    )
    account_counts = (
        accounts["ground_truth_label"].value_counts().reindex(GROUND_TRUTH_LABELS, fill_value=0)
    )
    for label, count in account_counts.items():
        lines.append(f"  {label}: {int(count)}")
    lines.append("")
    lines.append("Supported banks: " + ", ".join(item.bank_id for item in BANK_PROFILES))
    return "\n".join(lines) + "\n"


def _write_frame(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")


def generate_dataset(bank_id="BANK_01", output_dir=None):
    """Write accounts.csv, transactions.csv, and summary_report.txt for one bank."""
    profile = bank_profile(bank_id)
    transactions = build_transactions(profile)
    accounts = build_accounts(profile, transactions)
    validate_tables(accounts, transactions)

    destination = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    if output_dir is None and profile.bank_id != "BANK_01":
        destination = DEFAULT_OUTPUT_DIR / profile.bank_id

    accounts_path = destination / "accounts.csv"
    transactions_path = destination / "transactions.csv"
    summary_path = destination / "summary_report.txt"
    _write_frame(accounts_path, accounts)
    _write_frame(transactions_path, transactions)

    written_accounts = pd.read_csv(accounts_path, dtype=str)
    written_transactions = pd.read_csv(transactions_path, dtype=str)
    written_accounts["is_legitimate_decoy"] = written_accounts["is_legitimate_decoy"].map(
        {"True": True, "False": False}
    )
    validate_tables(written_accounts, written_transactions)

    report = summarize(profile, written_accounts, written_transactions)
    summary_path.write_text(report, encoding="utf-8")
    return {
        "bank_id": profile.bank_id,
        "seed": profile.seed,
        "accounts_path": accounts_path,
        "transactions_path": transactions_path,
        "summary_path": summary_path,
        "account_count": len(written_accounts),
        "transaction_count": len(written_transactions),
        "report": report,
    }


def main():
    """Generate the single-bank prototype files and print the summary."""
    written = generate_dataset("BANK_01")
    print(written["report"])
    print(f"Accounts: {written['accounts_path']}")
    print(f"Transactions: {written['transactions_path']}")
    print(f"Summary: {written['summary_path']}")


if __name__ == "__main__":
    main()
