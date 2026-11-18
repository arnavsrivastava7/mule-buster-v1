"""Evaluation metrics for Mule Buster Bank AI (Section 6).

PR-AUC, ROC-AUC, Recall@k%, Precision@k%, Confusion Matrix, Precision, Recall, F1,
and Merchant False-Positive Rate.
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)


def recall_precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k_percent: float) -> Tuple[float, float]:
    """Calculate recall and precision within the top k% highest risk scores."""
    n = len(y_true)
    if n == 0:
        return 0.0, 0.0
    k_count = max(1, int(np.ceil(n * (k_percent / 100.0))))
    order = np.argsort(y_score)[::-1]
    top_indices = order[:k_count]

    top_positives = np.sum(y_true[top_indices] == 1)
    total_positives = np.sum(y_true == 1)

    precision = float(top_positives / k_count)
    recall = float(top_positives / total_positives) if total_positives > 0 else 0.0
    return recall, precision


def merchant_fpr_at_threshold(
    eval_df: pd.DataFrame,
    score_col: str,
    threshold: float,
) -> Dict[str, float]:
    """Compute false positive rate specifically on merchant archetypes."""
    results = {}
    if "archetype" not in eval_df.columns:
        return results

    merchants = eval_df[eval_df["archetype"].astype(str).str.contains("MERCHANT|PAYROLL", case=False)]
    if len(merchants) == 0:
        return results

    # Overall merchant FPR
    flagged = np.sum(merchants[score_col] >= threshold)
    results["overall_merchant_fpr"] = float(flagged / len(merchants))

    # Per archetype breakdown
    for arch, grp in merchants.groupby("archetype"):
        cnt = len(grp)
        fp = np.sum(grp[score_col] >= threshold)
        results[f"{arch}_fpr"] = float(fp / cnt) if cnt > 0 else 0.0

    return results


def calculate_comprehensive_metrics(
    y_true: np.ndarray,
    y_score: np.ndarray,
    threshold: float = 50.0,
) -> Dict[str, Any]:
    """Compute all required metrics: PR-AUC, ROC-AUC, P, R, F1, and confusion matrix."""
    # Ensure binary predictions based on threshold
    y_pred = (y_score >= threshold).astype(int)

    # AUCs
    try:
        pr_auc = float(average_precision_score(y_true, y_score))
    except Exception:
        pr_auc = 0.0

    try:
        roc_auc = float(roc_auc_score(y_true, y_score))
    except Exception:
        roc_auc = 0.5

    # Classic metrics
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    # Top capacity metrics (top 1% and 2%)
    r1, p1 = recall_precision_at_k(y_true, y_score, 1.0)
    r2, p2 = recall_precision_at_k(y_true, y_score, 2.0)

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    return {
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "recall_at_1pct": r1,
        "precision_at_1pct": p1,
        "recall_at_2pct": r2,
        "precision_at_2pct": p2,
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "threshold": threshold,
    }
