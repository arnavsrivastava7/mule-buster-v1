"""Snapshot generation, labeling, and train/val/test dataset splitting.

Section 6:
- Sample is (account_id, as_of).
- Weekly snapshots over the data period.
- Labeling: Mule account snapshots are positive only when as_of >= mule_start_ts + 2d.
  Drop pre-onset mule snapshots from training.
- Group split by account_id (so no account appears in two sets).
- Time-forward split: train on earlier snapshots, test on the last ~25 days.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from bank_ai.config import Config
from bank_ai.features.build import build_feature_table, ML_FEATURES
from bank_ai.schemas import assert_features_exclude_labels


def make_snapshot_dates(
    txns: pd.DataFrame,
    step_days: int = 7,
    end_date: Optional[datetime] = None,
    start_date: Optional[datetime] = None,
) -> List[datetime]:
    """Generate weekly snapshot timestamps over the transaction timeframe."""
    ts_series = pd.to_datetime(txns["ts"], utc=True)
    min_ts = ts_series.min() if start_date is None else pd.Timestamp(start_date).tz_convert("UTC")
    max_ts = ts_series.max() if end_date is None else pd.Timestamp(end_date).tz_convert("UTC")

    # Start snapshots at least 7 days after the first recorded transaction so main window has context
    cur = min_ts + timedelta(days=7)
    dates = []
    while cur <= max_ts:
        dates.append(cur.to_pydatetime())
        cur += timedelta(days=step_days)

    if not dates or dates[-1] < max_ts:
        dates.append(max_ts.to_pydatetime())
    return dates


def make_snapshots(
    txns: pd.DataFrame,
    accounts: pd.DataFrame,
    cfg: Config,
    step_days: Optional[int] = None,
    as_of_dates: Optional[List[datetime]] = None,
) -> pd.DataFrame:
    """Build the feature table for all accounts across multiple as_of timestamps."""
    if as_of_dates is None:
        step = step_days or cfg.snapshot_step_days
        as_of_dates = make_snapshot_dates(txns, step_days=step)

    feature_table = build_feature_table(txns, accounts, as_of_dates, cfg)
    return feature_table


def label_snapshots(
    snapshots_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    cfg: Config,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Attach target label (is_mule) to snapshots following Section 6 labeling rules.

    Rules:
    - Mule account snapshots are positive (y=1) ONLY when as_of >= mule_start_ts + detection_delay_days (default 2d).
    - Pre-onset mule snapshots (before mule_start_ts + 2d) are dropped from training/eval set
      and returned as pre_onset_df for measuring days-to-detection.
    - All other accounts are negative (y=0).

    Returns:
        (labeled_snapshots_df, pre_onset_df)
    """
    merged = snapshots_df.merge(
        labels_df[["account_id", "is_mule", "mule_start_ts", "archetype"]],
        on="account_id",
        how="left",
    )

    merged["as_of_ts"] = pd.to_datetime(merged["as_of"], utc=True)
    merged["mule_start_utc"] = pd.to_datetime(merged["mule_start_ts"], utc=True)

    delay = timedelta(days=cfg.detection_delay_days)
    is_mule_acc = merged["is_mule"].fillna(False).astype(bool)

    # Criteria for positive target
    positive_mask = is_mule_acc & (
        merged["mule_start_utc"].isna() | (merged["as_of_ts"] >= (merged["mule_start_utc"] + delay))
    )

    # Pre-onset mule snapshots (mule account, but before mule onset + delay)
    pre_onset_mask = is_mule_acc & (
        ~merged["mule_start_utc"].isna() & (merged["as_of_ts"] < (merged["mule_start_utc"] + delay))
    )

    merged["target"] = 0
    merged.loc[positive_mask, "target"] = 1

    pre_onset_df = merged[pre_onset_mask].copy()
    valid_df = merged[~pre_onset_mask].copy()

    # Drop temporary datetime columns from final labeled table
    valid_df = valid_df.drop(columns=["as_of_ts", "mule_start_utc"])
    pre_onset_df = pre_onset_df.drop(columns=["as_of_ts", "mule_start_utc"])

    return valid_df, pre_onset_df


def group_split(
    df: pd.DataFrame,
    cfg: Config,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Primary split: group by account_id (70% train, 15% val, 15% test).

    Ensures no account appears in more than one partition.
    """
    groups = df["account_id"].values
    y = df["target"].values

    train_size = cfg.train_fraction
    val_size = cfg.validation_fraction
    test_size = 1.0 - train_size - val_size

    # First split: Train vs (Val + Test)
    gss1 = GroupShuffleSplit(n_splits=1, train_size=train_size, random_state=seed)
    train_idx, temp_idx = next(gss1.split(df, y, groups))
    train_df = df.iloc[train_idx].copy()
    temp_df = df.iloc[temp_idx].copy()

    # Second split: Val vs Test
    rel_val = val_size / (val_size + test_size)
    gss2 = GroupShuffleSplit(n_splits=1, train_size=rel_val, random_state=seed)
    val_sub_idx, test_sub_idx = next(gss2.split(temp_df, temp_df["target"].values, temp_df["account_id"].values))

    val_df = temp_df.iloc[val_sub_idx].copy()
    test_df = temp_df.iloc[test_sub_idx].copy()

    return train_df, val_df, test_df


def time_forward_split(
    df: pd.DataFrame,
    test_days: int = 25,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Secondary split: Time-forward test.

    Train on earlier snapshots, test on the final test_days.
    """
    ts_series = pd.to_datetime(df["as_of"], utc=True)
    cutoff = ts_series.max() - timedelta(days=test_days)

    train_df = df[ts_series <= cutoff].copy()
    test_df = df[ts_series > cutoff].copy()
    return train_df, test_df
