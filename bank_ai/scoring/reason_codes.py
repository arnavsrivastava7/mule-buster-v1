"""Turn fired rules and positive model contributions into short reason codes."""

from bank_ai.schemas import ReasonCode

CODE_CATALOG = {
    "MB_VEL_HIGH": {
        "feature": "velocity_ratio_24h",
        "direction": "above",
        "message": "Activity in last 24h is {v:.1f}× this account’s normal daily rate",
    },
    "MB_DWELL_SHORT": {
        "feature": "dwell_median_min",
        "direction": "below",
        "message": "Incoming funds leave after a median of {m:.0f} minutes",
    },
    "MB_PASSTHRU_HIGH": {
        "feature": "pass_through_ratio_7d",
        "direction": "above",
        "message": "{p:.0f}% of money received in 7 days was sent onward",
    },
    "MB_FANIN_HIGH": {
        "feature": "fan_in_7d",
        "direction": "above",
        "message": "Received from {n:.0f} different senders in 7 days",
    },
    "MB_FANOUT_HIGH": {
        "feature": "fan_out_7d",
        "direction": "above",
        "message": "Sent to {n:.0f} different payees in 7 days",
    },
    "MB_DORMANT_WAKE": {
        "feature": "dormancy_gap_days",
        "direction": "above",
        "message": "Account inactive {d:.0f} days, then {c:.0f} transactions this week",
    },
    "MB_NEWPAYEE_HIGH": {
        "feature": "new_payee_share_7d",
        "direction": "above",
        "message": "{s:.0f}% of outgoing payments went to first-time payees",
    },
    "MB_MERCHANT_MITIGATED": {
        "feature": None,
        "direction": None,
        "message": "Score reduced {k:.0f} points: stable merchant-like pattern",
    },
    "MB_INSUFFICIENT_DATA": {
        "feature": "txn_count_7d",
        "direction": None,
        "message": "Too little activity to score reliably",
    },
}


def _notable(code, row, cfg):
    """True when the feature is far enough from normal to mention."""
    spec = CODE_CATALOG[code]
    feature = spec["feature"]
    if feature is None:
        return True
    value = float(getattr(row, feature))
    if code == "MB_DORMANT_WAKE":
        return (
            value >= cfg.notable["dormancy_gap_days"]
            and float(row.txn_count_7d) >= cfg.dormancy_min_txn_count
        )
    cutoff = cfg.notable[feature]
    if spec["direction"] == "below":
        return value <= cutoff
    return value >= cutoff


def _message(code, row, adjustment):
    values = {
        "v": float(getattr(row, "velocity_ratio_24h", 0.0)),
        "m": float(getattr(row, "dwell_median_min", 0.0)),
        "p": 100 * float(getattr(row, "pass_through_ratio_7d", 0.0)),
        "n": float(getattr(row, "fan_in_7d", 0.0)),
        "d": float(getattr(row, "dormancy_gap_days", 0.0)),
        "c": float(getattr(row, "txn_count_7d", 0.0)),
        "s": 100 * float(getattr(row, "new_payee_share_7d", 0.0)),
        "k": float(adjustment),
    }
    if code == "MB_FANOUT_HIGH":
        values["n"] = float(getattr(row, "fan_out_7d", 0.0))
    return CODE_CATALOG[code]["message"].format(**values)


def _severity(points, total):
    if total <= 0:
        return "LOW"
    share = points / total
    if share >= 0.34:
        return "HIGH"
    if share >= 0.18:
        return "MEDIUM"
    return "LOW"


def insufficient_data_reason(row, cfg):
    """The only reason used when the activity gate skips the account."""
    count_failed = float(row.txn_count_7d) < cfg.min_txn_7d
    feature = "txn_count_7d" if count_failed else "total_in_7d"
    value = float(getattr(row, feature))
    threshold = float(cfg.min_txn_7d if count_failed else cfg.min_in_value)
    return [
        ReasonCode(
            code="MB_INSUFFICIENT_DATA",
            severity="LOW",
            feature=feature,
            value=value,
            threshold=threshold,
            points=0.0,
            message=CODE_CATALOG["MB_INSUFFICIENT_DATA"]["message"],
        )
    ]


def build_reason_codes(fired_rules, shap_top, row, cfg, adjustment):
    """Merge rule hits and positive contributions. Keep a code only if it is notable.

    At most four risk reasons are returned, plus the merchant note when a discount was applied.
    """
    by_code = {}
    for item in fired_rules:
        if not _notable(item["code"], row, cfg):
            continue
        by_code[item["code"]] = {
            "points": float(item["points"]),
            "feature": item["feature"],
            "value": float(item["value"]),
            "threshold": float(item["threshold"]),
        }

    feature_to_code = {
        spec["feature"]: code
        for code, spec in CODE_CATALOG.items()
        if spec["feature"] is not None and code != "MB_INSUFFICIENT_DATA"
    }
    for contribution in shap_top[:3]:
        code = feature_to_code.get(contribution["feature"])
        if code is None or code in by_code or not _notable(code, row, cfg):
            continue
        by_code[code] = {
            "points": float(max(contribution["shap"], 0.0)),
            "feature": contribution["feature"],
            "value": float(getattr(row, contribution["feature"])),
            "threshold": float(cfg.notable.get(contribution["feature"], 0.0)),
        }

    ranked = sorted(by_code.items(), key=lambda item: item[1]["points"], reverse=True)[:4]
    total = sum(item[1]["points"] for item in ranked)
    reasons = []
    for code, payload in ranked:
        reasons.append(
            ReasonCode(
                code=code,
                severity=_severity(payload["points"], total),
                feature=payload["feature"],
                value=payload["value"],
                threshold=payload["threshold"],
                points=payload["points"],
                message=_message(code, row, adjustment),
            )
        )
    if adjustment > 0:
        reasons.append(
            ReasonCode(
                code="MB_MERCHANT_MITIGATED",
                severity="LOW",
                feature=None,
                value=None,
                threshold=None,
                points=float(adjustment),
                message=_message("MB_MERCHANT_MITIGATED", row, adjustment),
            )
        )
    return reasons
