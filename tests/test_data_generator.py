"""Checks for the synthetic ledger: labels, files, seed, and three banks."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from data_generation.data_generator import build_accounts, build_transactions, generate_dataset
from data_generation.scenario_generator import BANK_PROFILES, bank_profile


class DataGeneratorTests(unittest.TestCase):
    def test_bank_one_matches_the_specification_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = generate_dataset("BANK_01", output_dir=first_dir)
            second = generate_dataset("BANK_01", output_dir=second_dir)
            first_text = Path(first["transactions_path"]).read_text(encoding="utf-8")
            second_text = Path(second["transactions_path"]).read_text(encoding="utf-8")
            self.assertEqual(first_text, second_text)
            self.assertEqual(first["account_count"], 100)
            self.assertEqual(first["transaction_count"], 320)

            transactions = pd.read_csv(first["transactions_path"], dtype=str)
            self.assertEqual(transactions.iloc[0]["transaction_id"], "TXN_0001")
            self.assertEqual(transactions.iloc[0]["sender_id"], "ACC_069")
            self.assertEqual(transactions.iloc[0]["amount"], "85000.00")
            self.assertEqual(transactions.iloc[-1]["transaction_id"], "TXN_0320")
            self.assertEqual(transactions.iloc[-1]["ground_truth_label"], "1_MULE_PASSTHROUGH")
            self.assertNotIn("predicted_label", transactions.columns)

            accounts = pd.read_csv(first["accounts_path"], dtype=str)
            employer = accounts.loc[accounts["account_id"] == "ACC_069"].iloc[0]
            self.assertEqual(employer["ground_truth_label"], "0_LEGITIMATE_DECOY_HIGH_ACTIVITY")
            self.assertEqual(employer["is_legitimate_decoy"], "True")

    def test_three_banks_share_scenarios_but_not_identities(self):
        frames = []
        for profile in BANK_PROFILES:
            transactions = build_transactions(profile)
            accounts = build_accounts(profile, transactions)
            frames.append((profile, accounts, transactions))
            self.assertEqual(profile.seed, bank_profile(profile.bank_id).seed)
            self.assertEqual(len(transactions), 320)
            self.assertEqual(len(accounts), 100)

        label_sets = [frame["ground_truth_label"].tolist() for _, _, frame in frames]
        self.assertEqual(label_sets[0], label_sets[1])
        self.assertEqual(label_sets[0], label_sets[2])

        account_ids = [set(frame["account_id"]) for _, frame, _ in frames]
        self.assertEqual(len(set.union(*account_ids)), 300)
        self.assertNotEqual(
            frames[0][1]["city_code"].tolist(),
            frames[1][1]["city_code"].tolist(),
        )
        self.assertTrue(frames[1][2].iloc[0]["timestamp"].startswith("2026-12-01T"))
        self.assertTrue(frames[2][2].iloc[0]["transaction_id"].startswith("B03_TXN_"))


if __name__ == "__main__":
    unittest.main()
