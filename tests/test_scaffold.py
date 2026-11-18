"""Confirm each placeholder module can be imported."""

import unittest

import bank_ai
import bank_ai.model
import central_ai
import central_ai.model
import data_generation
import data_generation.generate
import database
import database.db
import detection
import detection.risk


class ScaffoldTests(unittest.TestCase):
    def test_modules_are_placeholders(self):
        self.assertEqual(data_generation.STATUS, "ready")
        modules = (
            bank_ai,
            central_ai,
            detection,
            database,
        )
        for module in modules:
            self.assertIn(module.STATUS, ("placeholder", "ready"))

    def test_placeholder_functions_are_not_ready(self):
        self.assertFalse(bank_ai.model.score_accounts(None, None)["ready"])
        self.assertFalse(central_ai.model.review_bank_summaries(None)["ready"])
        self.assertFalse(detection.risk.assess_risk(None)["ready"])
        self.assertFalse(database.db.connect()["ready"])


if __name__ == "__main__":
    unittest.main()
