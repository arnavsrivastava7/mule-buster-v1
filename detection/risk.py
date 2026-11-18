"""Risk assessment and classification module for Mule Buster."""

from typing import Optional, Dict, Any
from detection.engine import InstantDetectionEngine


def assess_risk(scores: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assess risk score or transaction payload.
    
    Returns scaffold status if scores is None, or runs real assessment.
    """
    if scores is None:
        return {
            "ready": False,
            "message": "Risk assessment is not built yet.",
            "scores_received": False,
        }

    # If scores is a dict containing transaction data, run real detection
    if "sender_id" in scores and "receiver_id" in scores:
        engine = InstantDetectionEngine()
        return engine.evaluate_transaction(
            sender_id=scores["sender_id"],
            receiver_id=scores["receiver_id"],
            amount=scores.get("amount", 1000.0),
            channel=scores.get("channel", "TRANSFER"),
            timestamp=scores.get("timestamp"),
            persist=scores.get("persist", True),
        )

    # If raw numerical scores passed
    score_val = float(scores.get("score", 0.0))
    if score_val >= 80.0:
        band = "CRITICAL"
    elif score_val >= 60.0:
        band = "HIGH"
    elif score_val >= 40.0:
        band = "ELEVATED"
    else:
        band = "LOW"

    return {
        "ready": True,
        "risk_score": score_val,
        "risk_band": band,
        "action": "ESCALATE" if band in ("CRITICAL", "HIGH") else "MONITOR",
    }


__all__ = ["assess_risk", "InstantDetectionEngine"]
