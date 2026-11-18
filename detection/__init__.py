"""Turns model output into risk levels and review alerts."""

from detection.risk import assess_risk
from detection.engine import InstantDetectionEngine

MODULE_NAME = "Detection and risk assessment"
STATUS = "ready"

__all__ = ["MODULE_NAME", "STATUS", "assess_risk", "InstantDetectionEngine"]
