"""Cut one account's history into a time window that ends at as_of.

The window is (as_of - days, as_of]. Later payments are not included.
"""

from datetime import timedelta

import bisect


def window_bounds(timestamps, start, end):
    """Return the start and stop indexes for timestamps in (start, end]."""
    left = bisect.bisect_right(timestamps, start)
    right = bisect.bisect_right(timestamps, end)
    return left, right


def slice_window(records, as_of, days):
    """Return records whose time is inside the window ending at as_of."""
    start = as_of - timedelta(days=days)
    timestamps = [record["ts"] for record in records]
    left, right = window_bounds(timestamps, start, as_of)
    return records[left:right]
