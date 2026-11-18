"""Lower the score for stable merchant-like activity, with hard blocks.

A block means 'do not give the discount'. It does not hide the account.
"""


def merchant_likelihood(row, cfg):
    """Return a 0-1 score from the merchant-support signals."""
    weights = cfg.merchant_weights
    limits = cfg.merchant_thresholds
    category = getattr(row, "merchant_category", "") or ""
    registered = bool(row.is_registered_merchant) or (
        row.customer_type == "BUSINESS" and str(category) not in {"", "nan"}
    )
    likelihood = 0.0
    if registered:
        likelihood += weights["registered_or_business"]
    if float(row.account_age_days) >= limits["account_age_days"]:
        likelihood += weights["account_age_days"]
    if float(row.repeat_in_counterparty_share_90d) >= limits["repeat_in_counterparty_share_90d"]:
        likelihood += weights["repeat_payers"]
    stable_payee = (
        float(row.top_payee_value_share_7d) >= limits["top_payee_value_share_7d"]
        and float(row.top_payee_history_count) >= limits["top_payee_history_count"]
    )
    if stable_payee:
        likelihood += weights["stable_payee"]
    if float(row.active_days_30d) >= limits["active_days_30d"]:
        likelihood += weights["active_days"]
    return float(min(likelihood, 1.0))


def guard_blocks_discount(row, cfg):
    """True when a mule-like pattern must not receive the merchant discount."""
    block = cfg.merchant_block
    dormant_burst = (
        float(row.dormancy_gap_days) >= block["dormancy_gap_days"]
        and float(row.txn_count_7d) >= block["dormancy_min_txn_count"]
    )
    new_payees = float(row.new_payee_share_7d) >= block["new_payee_share_7d"]
    too_new = float(row.account_age_days) < block["min_account_age_days"]
    fast_fan_in = (
        float(row.fan_in_7d) >= block["fan_in_7d"]
        and float(row.dwell_median_min) <= block["dwell_median_min"]
        and float(row.new_payee_share_7d) >= block["new_payee_share_7d"]
    )
    return bool(dormant_burst or new_payees or too_new or fast_fan_in)


def merchant_adjustment(row, cfg):
    """Return points to subtract, and whether the guard blocked that discount."""
    blocked = guard_blocks_discount(row, cfg)
    likelihood = merchant_likelihood(row, cfg)
    if blocked:
        return 0, True, likelihood
    points = int(round(cfg.merchant_max_adjustment * likelihood))
    points = max(0, min(cfg.merchant_max_adjustment, points))
    return points, False, likelihood
