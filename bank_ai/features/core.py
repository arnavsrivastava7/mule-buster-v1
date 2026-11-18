"""The seven activity signals. Each function is the definition from the spec."""


def velocity_ratio(count_24h, count_prior_30d, cap):
    """How busy the last day is compared with the account's usual day.

    The prior window is the 30 days before that last day, not including it.
    """
    ratio = count_24h / ((count_prior_30d / 30) + 1)
    return float(min(ratio, cap))


def pass_through_ratio(total_in, total_out):
    """Share of the 7-day inflow that also left within 7 days."""
    if total_in <= 0:
        return 0.0
    return float(min(total_out, total_in) / total_in)


def distinct_counterparties(records, direction):
    """Count different counterparties for IN or OUT rows."""
    return float(len({row["counterparty_id"] for row in records if row["direction"] == direction}))


def dormancy_gap_days(last_before, first_inside, cap):
    """Days of silence between the previous payment and the first one in the window."""
    if last_before is None or first_inside is None:
        return 0.0
    gap = (first_inside - last_before).total_seconds() / 86400
    return float(min(max(gap, 0.0), cap))


def dormancy_shock(gap_days, txn_count_7d):
    """A 0-1 flag for 'quiet for a long time, then suddenly busy'."""
    return float((min(gap_days, 180) / 180) * (min(txn_count_7d, 20) / 20))


def new_payee_share(out_records, paid_before):
    """Share of outgoing payments whose payee was not paid before this window."""
    if not out_records:
        return 0.0
    new_count = sum(1 for row in out_records if row["counterparty_id"] not in paid_before)
    return float(new_count / len(out_records))
