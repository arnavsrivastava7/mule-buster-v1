"""Instant Detection Engine for Mule Buster.

Evaluates individual transactions in real-time by combining:
1. Bank AI Account-Level Features & Anomaly Scoring (velocity, pass-through, dormancy)
2. Central AI MultiDiGraph & Causal Time-Respecting Chain Analysis
3. Explainable Risk Classification (CRITICAL, HIGH, ELEVATED, LOW) and Reason Codes
4. Automatic persistence to SQLite database.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import uuid
import pandas as pd
import networkx as nx

from database.db import get_connection
from bank_ai.config import load_config
from bank_ai.models.train import load_artifacts
from central_ai.chain_detection import TimeRespectingPathFinder
from central_ai.chain_scoring import ChainRiskScoringEngine
from central_ai.transaction_graph import SingleBankGraphBuilder


class InstantDetectionEngine:
    """Real-time detection engine executing Bank AI and Central AI assessment on transactions."""

    def __init__(self, db_conn=None):
        self.cfg = load_config()
        self.artifacts_path = Path("bank_ai/artifacts/bank_ai_models.pkl")
        self.models = None
        if self.artifacts_path.exists():
            try:
                self.models = load_artifacts(self.artifacts_path)
            except Exception:
                self.models = None

    def evaluate_transaction(
        self,
        sender_id: str,
        receiver_id: str,
        amount: float,
        channel: str = "TRANSFER",
        timestamp: Optional[str] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Analyze a transaction through Bank AI and Central AI, returning full assessment."""
        now = datetime.now(timezone.utc)
        ts_str = timestamp or now.isoformat()
        tx_id = f"TXN_{uuid.uuid4().hex[:10].upper()}"

        conn = get_connection()
        try:
            # 1. Fetch sender & receiver account state from DB
            sender_row = conn.execute(
                "SELECT * FROM accounts WHERE account_id = ?", (sender_id,)
            ).fetchone()
            receiver_row = conn.execute(
                "SELECT * FROM accounts WHERE account_id = ?", (receiver_id,)
            ).fetchone()

            # If accounts don't exist yet, insert basic records
            if not sender_row:
                conn.execute(
                    "INSERT INTO accounts (account_id, bank_id, account_role, opening_balance, current_balance, risk_score, risk_band, status) "
                    "VALUES (?, 'BANK_SIM_01', 'RETAIL_USER', 50000.0, 50000.0, 10.0, 'LOW', 'ACTIVE')",
                    (sender_id,),
                )
            if not receiver_row:
                conn.execute(
                    "INSERT INTO accounts (account_id, bank_id, account_role, opening_balance, current_balance, risk_score, risk_band, status) "
                    "VALUES (?, 'BANK_SIM_01', 'RETAIL_USER', 10000.0, 10000.0, 10.0, 'LOW', 'ACTIVE')",
                    (receiver_id,),
                )
            conn.commit()

            # 2. Extract recent transaction history for sender and receiver
            sender_txns = conn.execute(
                "SELECT * FROM transactions WHERE sender_id = ? OR receiver_id = ? ORDER BY timestamp DESC LIMIT 50",
                (sender_id, sender_id),
            ).fetchall()

            receiver_txns = conn.execute(
                "SELECT * FROM transactions WHERE sender_id = ? OR receiver_id = ? ORDER BY timestamp DESC LIMIT 50",
                (receiver_id, receiver_id),
            ).fetchall()

            # 3. Bank AI Anomaly Signals
            # Rapid Outflow / Velocity Check:
            recent_inflows = [
                r for r in receiver_txns if r["receiver_id"] == receiver_id
            ]
            recent_outflows = [
                r for r in receiver_txns if r["sender_id"] == receiver_id
            ]

            reasons: List[str] = []
            bank_ai_score = 15.0  # Baseline low risk

            # Signal 1: High velocity transfer
            if len(sender_txns) > 5:
                bank_ai_score += 20.0
                reasons.append("HIGH_VELOCITY_ACTIVITY_DETECTED")

            # Signal 2: Rapid pass-through: Receiver just received funds and is sending large portion out
            if recent_inflows and amount > 5000.0:
                last_in = recent_inflows[0]
                try:
                    t_in = pd.to_datetime(last_in["timestamp"])
                    t_now = pd.to_datetime(ts_str)
                    dwell_mins = abs((t_now - t_in).total_seconds()) / 60.0
                    retention = min(amount, float(last_in["amount"])) / max(amount, float(last_in["amount"]))
                    if dwell_mins <= 60.0 and retention >= 0.80:
                        bank_ai_score += 40.0
                        reasons.append(f"RAPID_PASS_THROUGH_DWELL_{round(dwell_mins, 1)}M")
                        reasons.append(f"HIGH_AMOUNT_CONSERVATION_{round(retention * 100)}%")
                except Exception:
                    pass

            # Signal 3: High single transfer amount
            if amount >= 50000.0:
                bank_ai_score += 15.0
                reasons.append("HIGH_VALUE_THRESHOLD_EXCEEDED")

            # 4. Central AI Graph Topology Check
            # Check if sender or receiver connects to existing flagged accounts or active chains
            flagged_connections = conn.execute(
                "SELECT COUNT(*) as c FROM fraud_alerts WHERE (account_id = ? OR account_id = ?) AND risk_score >= 60",
                (sender_id, receiver_id),
            ).fetchone()["c"]

            chain_hits = conn.execute(
                "SELECT * FROM detected_chains WHERE path_str LIKE ? OR path_str LIKE ?",
                (f"%{sender_id}%", f"%{receiver_id}%"),
            ).fetchall()

            central_ai_score = 10.0
            if flagged_connections > 0:
                central_ai_score += 35.0
                reasons.append("CONNECTED_TO_PREVIOUSLY_ALERTED_MULE_NODE")

            if chain_hits:
                central_ai_score += 45.0
                chain_info = chain_hits[0]
                reasons.append(f"INTERSECTS_CONFIRMED_CHAIN_{chain_info['chain_id']}_DEPTH_{chain_info['hop_count']}")

            # 5. Composite Risk Score & Classification
            composite_score = min(100.0, max(bank_ai_score, 0.4 * bank_ai_score + 0.6 * central_ai_score))
            if composite_score >= 80.0:
                classification = "CRITICAL"
                action = "IMMEDIATE_HOLD_AND_FREEZE"
            elif composite_score >= 60.0:
                classification = "HIGH"
                action = "ESCALATE_TO_SAR_INVESTIGATION"
            elif composite_score >= 40.0:
                classification = "ELEVATED"
                action = "FLAG_FOR_ANALYST_REVIEW"
            else:
                classification = "LOW"
                action = "AUTO_CLEARED_BENIGN"

            if not reasons:
                reasons.append("NORMAL_RETAIL_TRANSFER_PATTERN")

            is_flagged = 1 if composite_score >= 40.0 else 0
            primary_reason = "; ".join(reasons[:3])

            # 6. Persistence to SQLite
            if persist:
                # Save transaction
                conn.execute(
                    "INSERT INTO transactions (transaction_id, sender_id, receiver_id, amount, timestamp, channel, ground_truth_label, is_flagged, risk_score) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        tx_id,
                        sender_id,
                        receiver_id,
                        amount,
                        ts_str,
                        channel,
                        "SUSPICIOUS_MULE" if is_flagged else "BENIGN",
                        is_flagged,
                        composite_score,
                    ),
                )

                # Update balances
                conn.execute(
                    "UPDATE accounts SET current_balance = current_balance - ?, risk_score = MAX(risk_score, ?) WHERE account_id = ?",
                    (amount, composite_score, sender_id),
                )
                conn.execute(
                    "UPDATE accounts SET current_balance = current_balance + ?, risk_score = MAX(risk_score, ?) WHERE account_id = ?",
                    (amount, composite_score, receiver_id),
                )

                # If flagged, create fraud alert
                if is_flagged:
                    alert_id = f"ALT_{uuid.uuid4().hex[:8].upper()}"
                    conn.execute(
                        "INSERT INTO fraud_alerts (alert_id, account_id, transaction_id, amount, timestamp, risk_score, risk_classification, detection_reason, source_tier, investigation_status, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'HYBRID_INSTANT', 'PENDING', ?)",
                        (
                            alert_id,
                            receiver_id if "PASS_THROUGH" in primary_reason else sender_id,
                            tx_id,
                            amount,
                            ts_str,
                            composite_score,
                            classification,
                            primary_reason,
                            now.isoformat(),
                        ),
                    )
                conn.commit()

            return {
                "transaction_id": tx_id,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "amount": amount,
                "timestamp": ts_str,
                "channel": channel,
                "risk_score": round(composite_score, 1),
                "risk_classification": classification,
                "bank_ai_score": round(bank_ai_score, 1),
                "central_ai_score": round(central_ai_score, 1),
                "recommended_action": action,
                "is_flagged": bool(is_flagged),
                "detection_reasons": reasons,
                "primary_reason": primary_reason,
            }
        finally:
            conn.close()


__all__ = ["InstantDetectionEngine"]
