"""Comprehensive Functional Pipeline Tests for Mule Buster.

Verifies end-to-end execution across:
1. Synthetic Data Generation
2. Bank AI Account Anomaly Assessment
3. Central AI Graph Topology & Chain Discovery
4. Instant Transaction Detection Engine
5. SQLite Database Storage & Persistence
6. Investigation Workflow & Audit Logging
"""

import unittest
from pathlib import Path
import tempfile
import sqlite3

from database.db import get_connection, init_db
from detection.engine import InstantDetectionEngine
from services.investigation_service import FraudInvestigationService


class FunctionalPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = FraudInvestigationService()
        cls.service.sync_database_from_pipeline()

    def test_database_populated_with_real_records(self):
        """Verify accounts and transactions are persisted in SQLite."""
        conn = get_connection()
        try:
            acc_count = conn.execute("SELECT COUNT(*) as c FROM accounts").fetchone()["c"]
            tx_count = conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"]
            alert_count = conn.execute("SELECT COUNT(*) as c FROM fraud_alerts").fetchone()["c"]
            chain_count = conn.execute("SELECT COUNT(*) as c FROM detected_chains").fetchone()["c"]

            self.assertGreaterEqual(acc_count, 10, "Accounts table must contain records")
            self.assertGreaterEqual(tx_count, 50, "Transactions table must contain records")
            self.assertGreaterEqual(alert_count, 1, "Fraud alerts must be populated")
            self.assertGreaterEqual(chain_count, 1, "Detected chains must be populated")
        finally:
            conn.close()

    def test_fraud_overview_metrics(self):
        """Verify get_fraud_overview returns non-zero, genuine metrics from DB."""
        overview = self.service.get_fraud_overview()
        self.assertGreater(overview["total_suspicious_accounts"], 0)
        self.assertGreater(overview["total_flagged_transactions"], 0)
        self.assertGreater(overview["total_flagged_value"], 0.0)
        self.assertIn("recent_alerts", overview)
        self.assertGreater(len(overview["recent_alerts"]), 0)

    def test_instant_detection_benign_transaction(self):
        """Test small transfer between new retail accounts produces LOW risk."""
        engine = InstantDetectionEngine()
        result = engine.evaluate_transaction(
            sender_id="TEST_BENIGN_01",
            receiver_id="TEST_BENIGN_02",
            amount=250.0,
            channel="UPI",
            persist=False,
        )
        self.assertEqual(result["risk_classification"], "LOW")
        self.assertFalse(result["is_flagged"])
        self.assertLess(result["risk_score"], 40.0)

    def test_instant_detection_suspicious_chain_transaction(self):
        """Test transfer intersecting known alerted accounts produces ELEVATED or HIGH risk."""
        engine = InstantDetectionEngine()
        result = engine.evaluate_transaction(
            sender_id="ACC_076",
            receiver_id="ACC_077",
            amount=98000.0,
            channel="TRANSFER",
            persist=True,
        )
        self.assertIn(result["risk_classification"], ("ELEVATED", "HIGH", "CRITICAL"))
        self.assertTrue(result["is_flagged"])
        self.assertGreaterEqual(result["risk_score"], 40.0)
        self.assertGreater(len(result["detection_reasons"]), 0)

    def test_account_investigation_details(self):
        """Test 360-degree forensic profile lookup."""
        details = self.service.get_suspicious_account_details("ACC_076")
        self.assertIsNotNone(details)
        self.assertIn("account", details)
        self.assertIn("total_inflow", details)
        self.assertIn("total_outflow", details)
        self.assertIn("pass_through_ratio", details)
        self.assertIn("inbound_transactions", details)
        self.assertIn("outbound_transactions", details)

    def test_investigation_management_workflow(self):
        """Test disposition update and audit trail logging in SQLite."""
        # Create an alert first
        engine = InstantDetectionEngine()
        eval_res = engine.evaluate_transaction(
            sender_id="ACC_080",
            receiver_id="ACC_081",
            amount=85000.0,
            channel="TRANSFER",
            persist=True,
        )
        alerts = self.service.get_fraud_alerts(search_account="ACC_080", limit=1)
        self.assertGreater(len(alerts), 0)
        alert_id = alerts[0]["alert_id"]

        # Update case disposition
        upd = self.service.update_investigation_status(
            alert_id=alert_id,
            account_id="ACC_080",
            new_status="CONFIRMED_MULE",
            notes="Identified as pass-through node in smurfing chain. Freezing account.",
            analyst_name="Lead Investigator",
        )
        self.assertTrue(upd["success"])

        # Check account details show audit trail
        acc_details = self.service.get_suspicious_account_details("ACC_080")
        audit_trail = acc_details["audit_trail"]
        self.assertGreater(len(audit_trail), 0)
        self.assertEqual(audit_trail[0]["action"], "DISPOSITION_CHANGED_TO_CONFIRMED_MULE")
        self.assertEqual(acc_details["account"]["status"], "FROZEN_MULE_CONFIRMED")


if __name__ == "__main__":
    unittest.main()
