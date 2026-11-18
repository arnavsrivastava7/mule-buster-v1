"""Synthetic banking dataset generator for Bank AI (Section 6).

Generates realistic accounts, transactions, and ground truth labels with
10 archetypes including legitimate merchants, payrolls, normal individuals,
and distinct money mule attack vectors (classic, dormant wake, camouflaged).
"""

from datetime import datetime, date, timedelta, timezone
from typing import Tuple, Optional
import numpy as np
import pandas as pd


def generate_bank(
    seed: int = 42,
    n_accounts: int = 1000,
    days: int = 120,
    mule_prevalence: float = 0.02,
    as_of_end: Optional[datetime] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate synthetic bank accounts, transactions, and ground-truth labels.

    Args:
        seed: Random seed for reproducibility.
        n_accounts: Number of accounts to simulate (~5,000 in full scale).
        days: Simulation timeline span in days (e.g. 120 days).
        mule_prevalence: Overall fraction of mule accounts (~2%).
        as_of_end: Anchor timestamp for the end of the simulation.

    Returns:
        (transactions_df, accounts_df, labels_df)
    """
    rng = np.random.default_rng(seed)
    if as_of_end is None:
        as_of_end = datetime(2026, 11, 15, 23, 59, 59, tzinfo=timezone.utc)
    start_time = as_of_end - timedelta(days=days)

    # 1. Assign archetypes according to Section 6 distribution
    archetype_weights = {
        "SALARIED_INDIVIDUAL": 0.70,
        "STUDENT_LOW_ACTIVITY": 0.08,
        "MERCHANT_RETAIL": 0.05,
        "MERCHANT_ECOMMERCE": 0.02,
        "PAYROLL_BUSINESS": 0.02,
        "CHARITY_FUNDRAISER": 0.01,
        "LEGIT_DORMANT_REVIVAL": 0.01,
        "MULE_CLASSIC": 0.010,
        "MULE_DORMANT_WAKE": 0.006,
        "MULE_CAMOUFLAGED": 0.004,
    }
    archetype_names = list(archetype_weights.keys())
    probs = np.array(list(archetype_weights.values()))
    probs = probs / probs.sum()

    assigned_archetypes = rng.choice(archetype_names, size=n_accounts, p=probs)

    accounts_list = []
    labels_list = []
    txns_list = []

    account_ids = [f"ACC_{i:06d}" for i in range(1, n_accounts + 1)]
    pool_size = max(100, int(n_accounts * 0.2))
    external_pool = [f"EXT_{i:05d}" for i in range(1, pool_size + 1)]

    # 2. Create account profiles and behavior parameters
    for i, acc_id in enumerate(account_ids):
        arch = assigned_archetypes[i]
        is_mule = arch.startswith("MULE")

        # Account opening date
        if arch == "LEGIT_DORMANT_REVIVAL" or arch == "MULE_DORMANT_WAKE":
            open_offset = rng.integers(180, 500)
        else:
            open_offset = rng.integers(30, 400)
        open_dt = (start_time - timedelta(days=int(open_offset))).date()

        # Customer type & merchant fields
        if "MERCHANT" in arch:
            customer_type = "BUSINESS"
            is_reg_merchant = True
            merchant_category = "RETAIL" if arch == "MERCHANT_RETAIL" else "ECOMMERCE"
        elif arch == "PAYROLL_BUSINESS":
            customer_type = "BUSINESS"
            is_reg_merchant = True
            merchant_category = "PAYROLL"
        elif arch == "CHARITY_FUNDRAISER":
            customer_type = "BUSINESS"
            is_reg_merchant = True
            merchant_category = "CHARITY"
        else:
            customer_type = "INDIVIDUAL"
            is_reg_merchant = False
            merchant_category = None

        accounts_list.append({
            "account_id": acc_id,
            "open_date": open_dt,
            "customer_type": customer_type,
            "is_registered_merchant": is_reg_merchant,
            "merchant_category": merchant_category,
        })

        # Mule timing
        mule_start = None
        mule_end = None
        if is_mule:
            # Active in the final 30-45 days of the simulation
            onset_day = rng.integers(int(days * 0.6), int(days * 0.85))
            mule_start = start_time + timedelta(days=int(onset_day))
            duration = rng.integers(5, 20)
            mule_end = mule_start + timedelta(days=int(duration))

        labels_list.append({
            "account_id": acc_id,
            "is_mule": is_mule,
            "mule_start_ts": mule_start,
            "mule_end_ts": mule_end,
            "archetype": arch,
        })

    accounts_df = pd.DataFrame(accounts_list)
    labels_df = pd.DataFrame(labels_list)

    # 3. Generate transaction ledger entries
    txn_counter = 1

    def make_txn(ts, acc_id, direction, amount, counterparty, is_internal=True, channel="TRANSFER"):
        nonlocal txn_counter
        t_id = f"TXN_{txn_counter:07d}_{direction}"
        txn_counter += 1
        return {
            "txn_id": t_id,
            "ts": ts.isoformat(),
            "account_id": acc_id,
            "direction": direction,
            "amount": round(float(amount), 2),
            "counterparty_id": counterparty,
            "counterparty_is_internal": is_internal,
            "channel": channel,
        }

    for i, acc_id in enumerate(account_ids):
        arch = assigned_archetypes[i]
        label_row = labels_list[i]

        if arch == "SALARIED_INDIVIDUAL":
            # Monthly salary IN, grocery / bills OUT, small regular payees
            cur_time = start_time
            salary_payer = rng.choice(external_pool[:10])
            stable_payees = rng.choice(external_pool[10:30], size=4, replace=False)

            while cur_time < as_of_end:
                # Monthly salary
                sal_amt = rng.uniform(40000, 120000)
                txns_list.append(make_txn(cur_time + timedelta(hours=rng.uniform(9, 11)), acc_id, "IN", sal_amt, salary_payer))
                # 8 to 15 small debits throughout the month
                for _ in range(rng.integers(8, 16)):
                    spend_dt = cur_time + timedelta(days=float(rng.uniform(1, 28)), hours=float(rng.uniform(8, 22)))
                    if spend_dt < as_of_end:
                        txns_list.append(make_txn(spend_dt, acc_id, "OUT", rng.uniform(200, 5000), rng.choice(stable_payees)))
                cur_time += timedelta(days=30)

        elif arch == "STUDENT_LOW_ACTIVITY":
            # Sparse pocket money IN, small snacks/UPI OUT
            num_tx = rng.integers(3, 10)
            parent = rng.choice(external_pool[30:50])
            for _ in range(num_tx):
                t_in = start_time + timedelta(days=float(rng.uniform(0, days)))
                txns_list.append(make_txn(t_in, acc_id, "IN", rng.uniform(1000, 5000), parent))
                for _ in range(rng.integers(1, 4)):
                    t_out = t_in + timedelta(days=float(rng.uniform(0.5, 4)))
                    if t_out < as_of_end:
                        txns_list.append(make_txn(t_out, acc_id, "OUT", rng.uniform(50, 400), rng.choice(external_pool[50:70])))

        elif arch == "MERCHANT_RETAIL":
            # Many repeat retail customers IN, daily/weekly sweep to 1 fixed settlement account
            settlement_partner = f"SETTLE_SUPPLIER_{acc_id[-4:]}"
            cur_time = start_time
            while cur_time < as_of_end:
                day_sales = 0
                for _ in range(rng.integers(4, 15)):
                    amt = rng.uniform(150, 2500)
                    day_sales += amt
                    txns_list.append(make_txn(cur_time + timedelta(hours=float(rng.uniform(10, 20))), acc_id, "IN", amt, rng.choice(external_pool[10:60])))
                # Sweep out 85-95% to fixed settlement supplier at end of day
                sweep_amt = day_sales * rng.uniform(0.85, 0.95)
                txns_list.append(make_txn(cur_time + timedelta(hours=22, minutes=float(rng.uniform(0, 30))), acc_id, "OUT", sweep_amt, settlement_partner))
                cur_time += timedelta(days=1)

        elif arch == "MERCHANT_ECOMMERCE":
            # High fan-in, regular settlement to 1-2 suppliers
            settle_1 = f"ECOMM_SUPPLIER_{acc_id[-4:]}"
            cur_time = start_time
            while cur_time < as_of_end:
                batch_in = 0
                for _ in range(rng.integers(6, 20)):
                    amt = rng.uniform(300, 4500)
                    batch_in += amt
                    txns_list.append(make_txn(cur_time + timedelta(hours=float(rng.uniform(8, 22))), acc_id, "IN", amt, rng.choice(external_pool)))
                # Settle every 2 days
                sweep_amt = batch_in * 0.90
                txns_list.append(make_txn(cur_time + timedelta(days=1, hours=23), acc_id, "OUT", sweep_amt, settle_1))
                cur_time += timedelta(days=2)

        elif arch == "PAYROLL_BUSINESS":
            # Large credit in, monthly salary fan-out to 20-50 employees
            cur_time = start_time
            while cur_time < as_of_end:
                capital_in = rng.uniform(500000, 2000000)
                txns_list.append(make_txn(cur_time, acc_id, "IN", capital_in, "CLIENT_PARENT_CORP"))
                emp_count = rng.integers(15, 35)
                for emp_idx in range(emp_count):
                    txns_list.append(make_txn(cur_time + timedelta(hours=float(rng.uniform(1, 8))), acc_id, "OUT", capital_in / emp_count, f"EMP_{acc_id[-3:]}_{emp_idx}"))
                cur_time += timedelta(days=30)

        elif arch == "CHARITY_FUNDRAISER":
            # Fan-in spike during campaign, funds held
            campaign_start = start_time + timedelta(days=float(rng.integers(20, 60)))
            for _ in range(rng.integers(20, 60)):
                txns_list.append(make_txn(campaign_start + timedelta(days=float(rng.uniform(0, 7)), hours=float(rng.uniform(0, 24))), acc_id, "IN", rng.uniform(100, 5000), rng.choice(external_pool)))
            # Only 10-20% spent out for admin/expenses
            txns_list.append(make_txn(campaign_start + timedelta(days=15), acc_id, "OUT", 5000, "VENDOR_CHARITY"))

        elif arch == "LEGIT_DORMANT_REVIVAL":
            # 60+ days silent, then genuine return with balance retention
            revival_dt = start_time + timedelta(days=float(rng.integers(70, 95)))
            deposit = rng.uniform(30000, 80000)
            txns_list.append(make_txn(revival_dt, acc_id, "IN", deposit, rng.choice(external_pool)))
            # Spend a fraction (30%), retain majority
            for _ in range(3):
                revival_dt += timedelta(days=float(rng.uniform(1, 3)))
                txns_list.append(make_txn(revival_dt, acc_id, "OUT", rng.uniform(1000, 4000), rng.choice(external_pool)))

        elif arch == "MULE_CLASSIC":
            # 6-20 senders in, money leaves within minutes to 1-3 new payees, retains <= 5%
            m_start = label_row["mule_start_ts"]
            m_end = label_row["mule_end_ts"]
            cur_burst = m_start
            mule_payees = [f"NEW_PAYEE_{acc_id[-4:]}_{j}" for j in range(3)]

            while cur_burst < m_end and cur_burst < as_of_end:
                in_count = rng.integers(6, 16)
                total_burst = 0
                burst_credits = []
                for _ in range(in_count):
                    amt = rng.uniform(5000, 25000)
                    total_burst += amt
                    credit_time = cur_burst + timedelta(minutes=float(rng.uniform(1, 60)))
                    burst_credits.append((credit_time, amt))
                    txns_list.append(make_txn(credit_time, acc_id, "IN", amt, rng.choice(external_pool)))

                # Rapid exit: 95%+ of funds out within 10-45 minutes after credits
                exit_time = max(t for t, _ in burst_credits) + timedelta(minutes=float(rng.uniform(5, 30)))
                out_amt = total_burst * rng.uniform(0.95, 0.99)
                txns_list.append(make_txn(exit_time, acc_id, "OUT", out_amt, rng.choice(mule_payees)))
                cur_burst += timedelta(days=float(rng.integers(3, 7)))

        elif arch == "MULE_DORMANT_WAKE":
            # Silent 60+ days, then burst pass-through in a tight window
            m_start = label_row["mule_start_ts"]
            burst_dt = m_start
            wake_payee = f"WAKE_DEST_{acc_id[-4:]}"
            total_wake = 0
            for _ in range(rng.integers(5, 12)):
                amt = rng.uniform(10000, 40000)
                total_wake += amt
                txns_list.append(make_txn(burst_dt, acc_id, "IN", amt, rng.choice(external_pool)))
                burst_dt += timedelta(minutes=float(rng.uniform(5, 25)))

            # Outflow within 30 minutes
            out_wake = total_wake * rng.uniform(0.94, 0.98)
            txns_list.append(make_txn(burst_dt + timedelta(minutes=15), acc_id, "OUT", out_wake, wake_payee))

        elif arch == "MULE_CAMOUFLAGED":
            # 60-75% pass-through over 2-3 days, mixed with normal-looking spend
            m_start = label_row["mule_start_ts"]
            c_time = m_start
            total_cam = 0
            for _ in range(rng.integers(4, 8)):
                amt = rng.uniform(15000, 35000)
                total_cam += amt
                txns_list.append(make_txn(c_time, acc_id, "IN", amt, rng.choice(external_pool)))
                c_time += timedelta(hours=float(rng.uniform(4, 12)))

            # Siphon 70% to new payee, 5% to local grocery, 25% retained
            target_payee = f"CAMO_OFFSHORE_{acc_id[-4:]}"
            txns_list.append(make_txn(c_time + timedelta(hours=18), acc_id, "OUT", total_cam * 0.70, target_payee))
            txns_list.append(make_txn(c_time + timedelta(hours=24), acc_id, "OUT", total_cam * 0.05, rng.choice(external_pool)))

    txns_df = pd.DataFrame(txns_list)
    txns_df = txns_df.sort_values("ts").reset_index(drop=True)

    return txns_df, accounts_df, labels_df
