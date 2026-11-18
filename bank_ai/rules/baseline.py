"""Transparent 0-100 score. Each fired rule records the evidence for a reason code."""


def _matching_tier(value, tiers, higher_is_riskier):
    """Return the highest-point tier whose cutoff the value crosses."""
    winner = None
    for tier in tiers:
        if higher_is_riskier and tier.minimum is not None and value >= tier.minimum:
            cutoff = tier.minimum
        elif not higher_is_riskier and tier.maximum is not None and value <= tier.maximum:
            cutoff = tier.maximum
        else:
            continue
        if winner is None or tier.points > winner[0]:
            winner = (tier.points, cutoff)
    return winner


def _fired(rule_id, code, feature, value, points, threshold):
    return {
        "rule_id": rule_id,
        "code": code,
        "feature": feature,
        "value": float(value),
        "points": float(points),
        "threshold": float(threshold),
    }


def score_rules(row, cfg):
    """Add rule points. The maxima in the config sum to 100."""
    fired = []
    specs = (
        ("R1", "velocity", "velocity_ratio_24h", True),
        ("R2", "dwell", "dwell_median_min", False),
        ("R3", "pass_through", "pass_through_ratio_7d", True),
        ("R4", "fan_in", "fan_in_7d", True),
        ("R5", "fan_out", "fan_out_7d", True),
        ("R7", "new_payees", "new_payee_share_7d", True),
    )
    codes = {
        "velocity": "MB_VEL_HIGH",
        "dwell": "MB_DWELL_SHORT",
        "pass_through": "MB_PASSTHRU_HIGH",
        "fan_in": "MB_FANIN_HIGH",
        "fan_out": "MB_FANOUT_HIGH",
        "new_payees": "MB_NEWPAYEE_HIGH",
    }
    for rule_id, name, feature, higher_is_riskier in specs:
        match = _matching_tier(float(getattr(row, feature)), cfg.rule_tiers[name], higher_is_riskier)
        if match is None:
            continue
        points, threshold = match
        fired.append(_fired(rule_id, codes[name], feature, getattr(row, feature), points, threshold))

    gap = float(row.dormancy_gap_days)
    if float(row.txn_count_7d) >= cfg.dormancy_min_txn_count:
        # R6 uses its own transaction-count gate. The tiers live in the config.
        match = _matching_tier(gap, cfg.rule_tiers["dormancy"], higher_is_riskier=True)
        if match is not None:
            points, threshold = match
            fired.append(
                _fired("R6", "MB_DORMANT_WAKE", "dormancy_gap_days", gap, points, threshold)
            )

    score = int(round(sum(item["points"] for item in fired)))
    return max(0, min(100, score)), fired
