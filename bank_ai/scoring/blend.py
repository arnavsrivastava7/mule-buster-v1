"""Combine the rule score and the model score, then assign a band."""


def blend_scores(ml_probability, rule_score, adjustment, cfg):
    """Return the model index, the blended total, and the final 0-100 score."""
    ml_score = int(round(100 * float(ml_probability)))
    ml_score = max(0, min(100, ml_score))
    blended = (cfg.ml_weight * ml_score) + (cfg.rule_weight * float(rule_score))
    final = int(round(blended) - int(adjustment))
    return ml_score, max(0, min(100, final))


def assign_band(score, cfg):
    """Map a score to a band and an advisory action. Nothing is frozen automatically."""
    if score >= cfg.band_critical:
        return "CRITICAL", "PRIORITY_REVIEW"
    if score >= cfg.band_high:
        return "HIGH", "ANALYST_REVIEW"
    if score >= cfg.band_medium:
        return "MEDIUM", "MONITOR"
    return "LOW", "NONE"


def lower_band(band):
    """Move a band down one step. LOW stays LOW. The account is still visible."""
    order = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    index = order.index(band)
    return order[min(index + 1, len(order) - 1)]
