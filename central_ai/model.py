"""Central AI module entry point and facade."""

from central_ai.final_assessment import MuleBusterCentralAI
from central_ai.pipeline import run_central_pipeline


def review_bank_summaries(scores):
    """Placeholder function for scaffold tests."""
    return {
        "ready": False,
        "message": "Review bank summaries placeholder.",
        "scores_received": scores is not None,
    }


__all__ = ["MuleBusterCentralAI", "run_central_pipeline", "review_bank_summaries"]
