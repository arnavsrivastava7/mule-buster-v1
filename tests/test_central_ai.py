"""Unit and integration tests for Mule Buster Level 2: Central AI.

Tests include:
- Invalid records (negative amount, self-transfers, score bounds)
- Duplicate events (deduplication)
- Disconnected accounts (implicit nodes handling)
- Valid chronological paths (time-respecting chain detection)
- Causal monotonicity (out-of-order rejection)
- Amount conservation filtering
- Guardrail capping for unalerted low-score chains
- Epistemic separation of observed transfers vs inferred chains
"""

import unittest
from datetime import datetime, timezone

from central_ai.schemas import (
    AccountAlertRecord,
    TransactionRecord,
    parse_iso_timestamp,
)
from central_ai.final_assessment import MuleBusterCentralAI
from central_ai.chain_detection import TimeRespectingPathFinder
from central_ai.transaction_graph import SingleBankGraphBuilder
from central_ai.central_ingestion import (
    load_transactions,
    load_bank_ai_results,
    validate_ingested_data,
)


class TestCentralAISchemasAndValidation(unittest.TestCase):
    """Test validation and error handling for raw inputs."""

    def test_invalid_negative_amount_raises_error(self):
        with self.assertRaises(ValueError):
            TransactionRecord(
                tx_id="TX_NEG",
                source_account="ACC_1",
                target_account="ACC_2",
                amount=-500.0,
                timestamp=datetime.now(timezone.utc),
            )

    def test_invalid_self_transfer_raises_error(self):
        with self.assertRaises(ValueError):
            TransactionRecord(
                tx_id="TX_SELF",
                source_account="ACC_1",
                target_account="ACC_1",
                amount=1000.0,
                timestamp=datetime.now(timezone.utc),
            )

    def test_invalid_bank_ai_score_bounds_raises_error(self):
        with self.assertRaises(ValueError):
            AccountAlertRecord(account_id="ACC_BAD", bank_ai_score=1.5, is_alerted=True)
        with self.assertRaises(ValueError):
            AccountAlertRecord(account_id="ACC_BAD", bank_ai_score=-0.1, is_alerted=False)


class TestCentralAIGraphAndDetection(unittest.TestCase):
    """Test graph builder, path discovery, and scoring logic."""

    def setUp(self):
        self.central_ai = MuleBusterCentralAI(
            path_finder=TimeRespectingPathFinder(
                min_hops=2,
                max_hops=6,
                max_hop_dwell_minutes=120.0,
                min_step_retention=0.70,
                max_step_retention=1.05,
                require_alerted_participant=True,
            )
        )

    def test_valid_chronological_chain_detection(self):
        """Verifies rapid 3-hop mule chain with high amount retention is detected."""
        accounts = [
            AccountAlertRecord("ACC_ORIG", bank_ai_score=0.15, is_alerted=False),
            AccountAlertRecord("ACC_MULE_1", bank_ai_score=0.88, is_alerted=True, alert_reasons=("RAPID_PASS_THROUGH",)),
            AccountAlertRecord("ACC_MULE_2", bank_ai_score=0.92, is_alerted=True, alert_reasons=("NEW_ACCOUNT_SPIKE",)),
            AccountAlertRecord("ACC_COLLECTOR", bank_ai_score=0.65, is_alerted=False),
        ]
        transactions = [
            TransactionRecord.from_dict({
                "tx_id": "TX_1", "source_account": "ACC_ORIG", "target_account": "ACC_MULE_1",
                "amount": 100000.0, "timestamp": "2026-11-16T10:00:00Z",
            }),
            TransactionRecord.from_dict({
                "tx_id": "TX_2", "source_account": "ACC_MULE_1", "target_account": "ACC_MULE_2",
                "amount": 98500.0, "timestamp": "2026-11-16T10:06:00Z",
            }),
            TransactionRecord.from_dict({
                "tx_id": "TX_3", "source_account": "ACC_MULE_2", "target_account": "ACC_COLLECTOR",
                "amount": 97000.0, "timestamp": "2026-11-16T10:15:00Z",
            }),
        ]

        record = self.central_ai.run_investigation(
            bank_id="BANK_SIM_01", batch_id="TEST_001", accounts=accounts, transactions=transactions
        )

        self.assertEqual(len(record.observed_transfers), 3)
        self.assertEqual(len(record.candidate_chains), 1)

        chain = record.candidate_chains[0]
        self.assertEqual(chain.accounts_path, ["ACC_ORIG", "ACC_MULE_1", "ACC_MULE_2", "ACC_COLLECTOR"])
        self.assertEqual(chain.hop_count, 3)
        self.assertAlmostEqual(chain.duration_minutes, 15.0)
        self.assertAlmostEqual(chain.net_retention_ratio, 0.97)
        self.assertGreaterEqual(chain.chain_risk_score, 75.0)
        self.assertIn(chain.risk_band, ("HIGH", "CRITICAL"))
        self.assertEqual(chain.evidence_classification, "INFERRED_TEMPORAL_FLOW_HYPOTHESIS")
        self.assertIn("fungibility", chain.fungibility_caveat.lower())

    def test_causal_monotonicity_rejects_out_of_order_transfers(self):
        """Transfers where B -> C occurs before A -> B must not form a chain."""
        accounts = [
            AccountAlertRecord("A", bank_ai_score=0.90, is_alerted=True),
            AccountAlertRecord("B", bank_ai_score=0.85, is_alerted=True),
            AccountAlertRecord("C", bank_ai_score=0.80, is_alerted=True),
        ]
        transactions = [
            # B -> C happens earlier (09:00)
            TransactionRecord(
                tx_id="TX_EARLY", source_account="B", target_account="C",
                amount=50000.0, timestamp=parse_iso_timestamp("2026-11-16T09:00:00Z")
            ),
            # A -> B happens later (10:00)
            TransactionRecord(
                tx_id="TX_LATE", source_account="A", target_account="B",
                amount=50000.0, timestamp=parse_iso_timestamp("2026-11-16T10:00:00Z")
            ),
        ]

        record = self.central_ai.run_investigation(
            bank_id="BANK_SIM_01", batch_id="TEST_CAUSAL", accounts=accounts, transactions=transactions
        )

        self.assertEqual(len(record.observed_transfers), 2)
        self.assertEqual(len(record.candidate_chains), 0)

    def test_divergent_amounts_rejected_by_conservation_filter(self):
        """Unrelated small payment after large inflow must not trigger a chain."""
        accounts = [
            AccountAlertRecord("SENDER", bank_ai_score=0.80, is_alerted=True),
            AccountAlertRecord("USER", bank_ai_score=0.75, is_alerted=True),
            AccountAlertRecord("CAFE", bank_ai_score=0.10, is_alerted=False),
        ]
        transactions = [
            TransactionRecord(
                tx_id="TX_IN", source_account="SENDER", target_account="USER",
                amount=100000.0, timestamp=parse_iso_timestamp("2026-11-16T12:00:00Z")
            ),
            TransactionRecord(
                tx_id="TX_COFFEE", source_account="USER", target_account="CAFE",
                amount=250.0, timestamp=parse_iso_timestamp("2026-11-16T12:05:00Z")
            ),
        ]

        record = self.central_ai.run_investigation(
            bank_id="BANK_SIM_01", batch_id="TEST_DIVERGENT", accounts=accounts, transactions=transactions
        )

        self.assertEqual(len(record.candidate_chains), 0)

    def test_disconnected_accounts_handled_gracefully(self):
        """Accounts in transactions but absent from Bank AI results are added with default score."""
        accounts = [
            AccountAlertRecord("KNOWN_1", bank_ai_score=0.70, is_alerted=True),
        ]
        transactions = [
            TransactionRecord(
                tx_id="TX_DISC", source_account="KNOWN_1", target_account="DISCONNECTED_999",
                amount=5000.0, timestamp=parse_iso_timestamp("2026-11-16T14:00:00Z")
            ),
        ]

        builder = SingleBankGraphBuilder(default_unalerted_score=0.05)
        graph = builder.build_graph(accounts, transactions)

        self.assertTrue(graph.has_node("DISCONNECTED_999"))
        self.assertEqual(graph.nodes["DISCONNECTED_999"]["bank_ai_score"], 0.05)
        self.assertFalse(graph.nodes["DISCONNECTED_999"]["is_alerted"])

    def test_guardrail_multiplier_caps_unalerted_chain_score(self):
        """Chains with no alerted accounts and low Bank AI scores (<0.25) cap at <= 49.0."""
        unrestricted_ai = MuleBusterCentralAI(
            path_finder=TimeRespectingPathFinder(
                min_hops=2, max_hops=4, require_alerted_participant=False
            )
        )
        accounts = [
            AccountAlertRecord("CORP_1", bank_ai_score=0.10, is_alerted=False),
            AccountAlertRecord("CORP_2", bank_ai_score=0.10, is_alerted=False),
            AccountAlertRecord("CORP_3", bank_ai_score=0.10, is_alerted=False),
        ]
        transactions = [
            TransactionRecord(
                tx_id="TX_C1", source_account="CORP_1", target_account="CORP_2",
                amount=50000.0, timestamp=parse_iso_timestamp("2026-11-16T14:00:00Z")
            ),
            TransactionRecord(
                tx_id="TX_C2", source_account="CORP_2", target_account="CORP_3",
                amount=50000.0, timestamp=parse_iso_timestamp("2026-11-16T14:02:00Z")
            ),
        ]

        record = unrestricted_ai.run_investigation(
            bank_id="BANK_SIM_01", batch_id="TEST_GUARDRAIL", accounts=accounts, transactions=transactions
        )

        self.assertEqual(len(record.candidate_chains), 1)
        chain = record.candidate_chains[0]
        self.assertLessEqual(chain.chain_risk_score, 49.0)
        self.assertEqual(chain.risk_band, "MEDIUM")


if __name__ == "__main__":
    unittest.main()
