"""Build one feature row per account at each as_of timestamp.

Only payments at or before as_of are visible. That is what stops future
payments from leaking into today's score.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from bank_ai.features.core import (
    distinct_counterparties,
    dormancy_gap_days,
    dormancy_shock,
    new_payee_share,
    pass_through_ratio,
    velocity_ratio,
)
from bank_ai.features.dwell import dwell_features
from bank_ai.features.merchant_support import (
    active_days,
    repeat_in_counterparty_share,
    top_payee_stats,
)
from bank_ai.features.windows import window_bounds
from bank_ai.schemas import FORBIDDEN_FEATURE_COLUMNS

# Columns the model is allowed to see. Order is also the monotone-constraint order.
ML_FEATURES = (
    "txn_count_7d",
    "velocity_ratio_24h",
    "dwell_median_min",
    "share_out_within_60m",
    "pass_through_ratio_7d",
    "fan_in_7d",
    "fan_out_7d",
    "dormancy_gap_days",
    "dormancy_shock",
    "new_payee_share_7d",
    "account_age_days",
    "log_total_in_7d",
    "log_total_out_7d",
)

MONOTONE_CONSTRAINTS = {
    "velocity_ratio_24h": 1,
    "pass_through_ratio_7d": 1,
    "fan_in_7d": 1,
    "fan_out_7d": 1,
    "dormancy_shock": 1,
    "new_payee_share_7d": 1,
    "dwell_median_min": -1,
}

MERCHANT_FEATURES = (
    "repeat_in_counterparty_share_90d",
    "top_payee_value_share_7d",
    "top_payee_history_count",
    "active_days_30d",
)


def monotone_vector():
    """+1 means a larger value may only raise risk. -1 means it may only lower risk."""
    return [MONOTONE_CONSTRAINTS.get(name, 0) for name in ML_FEATURES]


def _records_by_account(transactions):
    """Sort each account's payments once. Later windows are slices of this list."""
    frame = transactions.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values(["account_id", "ts", "txn_id"])
    grouped = {}
    for account_id, group in frame.groupby("account_id", sort=False):
        grouped[account_id] = [
            {
                "ts": timestamp.to_pydatetime(),
                "direction": direction,
                "amount": float(amount),
                "counterparty_id": counterparty,
            }
            for timestamp, direction, amount, counterparty in zip(
                group["ts"],
                group["direction"],
                group["amount"],
                group["counterparty_id"],
            )
        ]
    return grouped


def _sum_amount(records, direction):
    return float(sum(row["amount"] for row in records if row["direction"] == direction))


def _prior_out_counts(records, start_index):
    counts = {}
    for row in records[:start_index]:
        if row["direction"] == "OUT":
            counts[row["counterparty_id"]] = counts.get(row["counterparty_id"], 0) + 1
    return counts


def features_at(records, as_of, open_date, profile, cfg):
    """Calculate every feature for one account using only history up to as_of."""
    timestamps = [row["ts"] for row in records]
    main_start = as_of - timedelta(days=cfg.main_days)
    recent_start = as_of - timedelta(days=cfg.recent_days)
    prior_start = as_of - timedelta(days=cfg.baseline_offset_days)
    prior_end = as_of - timedelta(days=cfg.recent_days)
    lookback_start = as_of - timedelta(days=cfg.lookback_days)
    active_start = as_of - timedelta(days=cfg.baseline_days)

    main_left, main_right = window_bounds(timestamps, main_start, as_of)
    recent_left, recent_right = window_bounds(timestamps, recent_start, as_of)
    prior_left, prior_right = window_bounds(timestamps, prior_start, prior_end)
    lookback_left, lookback_right = window_bounds(timestamps, lookback_start, as_of)
    active_left, active_right = window_bounds(timestamps, active_start, as_of)

    main = records[main_left:main_right]
    lookback = records[lookback_left:lookback_right]
    total_in = _sum_amount(main, "IN")
    total_out = _sum_amount(main, "OUT")
    outs = [row for row in main if row["direction"] == "OUT"]
    ins = [row for row in main if row["direction"] == "IN"]
    dwell = dwell_features([(row["ts"], row["direction"], row["amount"]) for row in main])
    paid_before = _prior_out_counts(records, main_left)
    gap = 0.0
    if main:
        last_before = timestamps[main_left - 1] if main_left > 0 else None
        gap = dormancy_gap_days(last_before, main[0]["ts"], cfg.dormancy_cap_days)
    txn_count = float(len(main))
    top_share, top_history = top_payee_stats(outs, paid_before)
    age_days = float((as_of.date() - open_date).days)
    if age_days < 0:
        age_days = 0.0

    row = {
        "txn_count_7d": txn_count,
        "velocity_ratio_24h": velocity_ratio(
            float(recent_right - recent_left),
            float(prior_right - prior_left),
            cfg.velocity_cap,
        ),
        "dwell_median_min": dwell["dwell_median_min"],
        "share_out_within_60m": dwell["share_out_within_60m"],
        "pass_through_ratio_7d": pass_through_ratio(total_in, total_out),
        "fan_in_7d": distinct_counterparties(main, "IN"),
        "fan_out_7d": distinct_counterparties(main, "OUT"),
        "dormancy_gap_days": gap,
        "dormancy_shock": dormancy_shock(gap, txn_count),
        "new_payee_share_7d": new_payee_share(outs, set(paid_before)),
        "account_age_days": age_days,
        "log_total_in_7d": float(np.log1p(total_in)),
        "log_total_out_7d": float(np.log1p(total_out)),
        "total_in_7d": total_in,
        "total_out_7d": total_out,
        "repeat_in_counterparty_share_90d": repeat_in_counterparty_share(
            [row for row in lookback if row["direction"] == "IN"]
        ),
        "top_payee_value_share_7d": top_share,
        "top_payee_history_count": top_history,
        "active_days_30d": active_days(records[active_left:active_right]),
        "customer_type": profile["customer_type"],
        "is_registered_merchant": bool(profile["is_registered_merchant"]),
        "merchant_category": profile["merchant_category"],
    }
    row["gated"] = bool(
        row["txn_count_7d"] < cfg.min_txn_7d or row["total_in_7d"] < cfg.min_in_value
    )
    return row


def build_feature_table(transactions, accounts, as_of_dates, cfg):
    """Stack feature rows. Label columns on the inputs are ignored."""
    leaked = FORBIDDEN_FEATURE_COLUMNS.intersection(transactions.columns)
    if leaked:
        transactions = transactions.drop(columns=list(leaked))
    history = _records_by_account(transactions)
    profiles = {}
    for account in accounts.itertuples(index=False):
        open_date = account.open_date
        if not hasattr(open_date, "year"):
            open_date = pd.to_datetime(open_date).date()
        category = account.merchant_category
        if category is None or (isinstance(category, float) and np.isnan(category)):
            category = ""
        profiles[account.account_id] = {
            "open_date": open_date,
            "customer_type": account.customer_type,
            "is_registered_merchant": bool(account.is_registered_merchant),
            "merchant_category": "" if pd.isna(category) else str(category),
        }

    rows = []
    moments = [pd.Timestamp(value).tz_convert("UTC").to_pydatetime() for value in as_of_dates]
    for account_id, profile in profiles.items():
        records = history.get(account_id, [])
        for as_of in moments:
            features = features_at(records, as_of, profile["open_date"], profile, cfg)
            features["account_id"] = account_id
            features["as_of"] = as_of
            rows.append(features)
    frame = pd.DataFrame(rows)
    overlap = FORBIDDEN_FEATURE_COLUMNS.intersection(frame.columns)
    if overlap:
        frame = frame.drop(columns=list(overlap))
    return frame
