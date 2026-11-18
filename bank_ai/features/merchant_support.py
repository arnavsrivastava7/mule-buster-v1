"""Signals used only by the merchant guard.

They are not model inputs. A model that sees them can learn
'this looks like a shop, so it is safe', which is the shortcut a fake shop would use.
"""

from collections import defaultdict


def repeat_in_counterparty_share(in_records):
    """Share of inbound value from payers who paid at least twice in the lookback."""
    if not in_records:
        return 0.0
    counts = defaultdict(int)
    totals = defaultdict(float)
    for row in in_records:
        counts[row["counterparty_id"]] += 1
        totals[row["counterparty_id"]] += row["amount"]
    inbound = sum(totals.values())
    if inbound <= 0:
        return 0.0
    repeated = sum(amount for party, amount in totals.items() if counts[party] >= 2)
    return float(repeated / inbound)


def top_payee_stats(out_records, paid_before_counts):
    """Share of outbound value sent to the biggest payee, and how often they were paid before."""
    if not out_records:
        return 0.0, 0.0
    totals = defaultdict(float)
    for row in out_records:
        totals[row["counterparty_id"]] += row["amount"]
    outbound = sum(totals.values())
    if outbound <= 0:
        return 0.0, 0.0
    top_payee = max(totals, key=totals.get)
    return float(totals[top_payee] / outbound), float(paid_before_counts.get(top_payee, 0))


def active_days(records):
    """How many different dates have at least one entry."""
    return float(len({row["ts"].date() for row in records}))
