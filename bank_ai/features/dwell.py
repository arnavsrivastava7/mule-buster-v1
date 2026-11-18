"""How long incoming money stays before it is spent.

Matching is first-in, first-out and uses only entries inside the window.
Money spent from a balance that arrived before the window is ignored.
"""

from collections import deque

import numpy as np


def dwell_features(entries):
    """Return dwell_median_min and share_out_within_60m.

    entries is a list of (timestamp, direction, amount), sorted by time.
    direction is IN or OUT.
    """
    credits = deque()
    samples = []
    for ts, direction, amount in entries:
        if direction == "IN":
            credits.append([ts, amount])
            continue
        remaining = amount
        while remaining > 1e-9 and credits:
            credit_ts, credit_amount = credits[0]
            used = min(remaining, credit_amount)
            samples.append(((ts - credit_ts).total_seconds() / 60, used))
            remaining -= used
            credits[0][1] -= used
            if credits[0][1] <= 1e-9:
                credits.popleft()

    if not samples:
        return {"dwell_median_min": 10080.0, "share_out_within_60m": 0.0}

    durations = np.array([sample[0] for sample in samples])
    weights = np.array([sample[1] for sample in samples])
    order = np.argsort(durations)
    durations = durations[order]
    weights = weights[order]
    median = durations[np.searchsorted(np.cumsum(weights), weights.sum() / 2)]
    return {
        "dwell_median_min": float(min(median, 10080)),
        "share_out_within_60m": float(weights[durations <= 60].sum() / weights.sum()),
    }
