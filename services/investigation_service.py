"""Unified Fraud Investigation Service.

Bridges Bank AI, Central AI, Instant Detection, and SQLite Database
to power the user-facing fraud detection & investigation workflows.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import uuid
import pandas as pd

from database.db import get_connection, init_db, DB_PATH
from detection.engine import InstantDetectionEngine
from data_generation.generate import generate_bank_data


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FraudInvestigationService:
    """Service providing fraud investigation operations and database queries."""

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.db_path = DB_PATH
        # Ensure database is initialized
        if not self.db_path.exists():
            init_db()

    def sync_database_from_pipeline(self) -> Dict[str, Any]:
        """Load data from raw CSVs, Bank AI, and Central AI results into SQLite."""
        init_db()
        conn = get_connection()
        try:
            # 1. Accounts
            acc_path = self.project_root / "data" / "raw" / "accounts.csv"
            if not acc_path.exists():
                generate_bank_data()

            acc_df = pd.read_csv(acc_path)
            for _, r in acc_df.iterrows():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO accounts 
                    (account_id, bank_id, account_role, is_registered_merchant, city_code, opened_on, opening_balance, current_balance, risk_score, risk_band, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 15.0, 'LOW', 'ACTIVE')
                    """,
                    (
                        str(r["account_id"]),
                        str(r.get("bank_id", "BANK_SIM_01")),
                        str(r.get("account_role", "RETAIL_USER")),
                        1 if "MERCHANT" in str(r.get("account_role", "")).upper() else 0,
                        str(r.get("city_code", "MUM")),
                        str(r.get("opened_on", "2025-01-01")),
                        float(r.get("opening_balance_inr", 50000.0)),
                        float(r.get("opening_balance_inr", 50000.0)),
                    ),
                )

            # 2. Transactions
            tx_path = self.project_root / "data" / "raw" / "transactions.csv"
            if tx_path.exists():
                tx_df = pd.read_csv(tx_path)
                for _, r in tx_df.iterrows():
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO transactions
                        (transaction_id, sender_id, receiver_id, amount, timestamp, channel, ground_truth_label, is_flagged, risk_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(r["transaction_id"]),
                            str(r["sender_id"]),
                            str(r["receiver_id"]),
                            float(r["amount"]),
                            str(r["timestamp"]),
                            str(r.get("transaction_type", "TRANSFER")),
                            str(r.get("ground_truth_label", "BENIGN")),
                            1 if "MULE" in str(r.get("ground_truth_label", "")).upper() else 0,
                            80.0 if "MULE" in str(r.get("ground_truth_label", "")).upper() else 10.0,
                        ),
                    )

            # 3. Ingest Bank AI results
            bank_res_path = self.project_root / "bank_ai" / "results" / "bank_ai_results.csv"
            if bank_res_path.exists():
                b_df = pd.read_csv(bank_res_path)
                for _, r in b_df.iterrows():
                    conn.execute(
                        """
                        UPDATE accounts
                        SET risk_score = ?, risk_band = ?
                        WHERE account_id = ?
                        """,
                        (float(r["risk_score"]), str(r["risk_band"]), str(r["account_id"])),
                    )

            # 4. Ingest Bank Alerts
            bank_alt_path = self.project_root / "bank_ai" / "results" / "bank_alerts.csv"
            if bank_alt_path.exists():
                balt_df = pd.read_csv(bank_alt_path)
                for _, r in balt_df.iterrows():
                    alt_id = f"ALT_BNK_{str(r['account_id'])}"
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO fraud_alerts
                        (alert_id, account_id, transaction_id, amount, timestamp, risk_score, risk_classification, detection_reason, source_tier, investigation_status, created_at)
                        VALUES (?, ?, NULL, 0.0, ?, ?, ?, ?, 'BANK_AI', 'PENDING', ?)
                        """,
                        (
                            alt_id,
                            str(r["account_id"]),
                            str(r.get("as_of", datetime.now(timezone.utc).isoformat())),
                            float(r["risk_score"]),
                            str(r["risk_band"]),
                            f"Action: {r.get('action', 'REVIEW')} | Rapid Velocity & Retention Anomaly",
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )

            # 5. Ingest Central AI detected chains
            central_res_path = self.project_root / "central_ai" / "results" / "central_results.csv"
            if central_res_path.exists():
                c_df = pd.read_csv(central_res_path)
                for _, r in c_df.iterrows():
                    cid = str(r["chain_id"])
                    path_str = str(r.get("accounts_path", r.get("path_str", "")))
                    score = float(r.get("chain_risk_score", r.get("risk_score", 80.0)))
                    cls = str(r.get("risk_band", r.get("evidence_classification", "CRITICAL")))
                    reasons = str(r.get("explanation_codes", r.get("reason_codes", "")))
                    duration = float(r.get("duration_minutes", r.get("total_duration_minutes", 15.0)))
                    retention = float(r.get("net_retention_ratio", 0.95)) * 100
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO detected_chains
                        (chain_id, path_str, hop_count, duration_minutes, retention_pct, risk_score, classification, reason_codes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cid,
                            path_str,
                            int(r.get("hop_count", 2)),
                            duration,
                            retention,
                            score,
                            cls,
                            reasons,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )

                    # Extract accounts in path and create alerts for them
                    accounts_in_path = [a.strip() for a in path_str.split("->") if a.strip()]
                    for acc in accounts_in_path:
                        c_alt_id = f"ALT_CEN_{cid}_{acc}"
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO fraud_alerts
                            (alert_id, account_id, transaction_id, amount, timestamp, risk_score, risk_classification, detection_reason, source_tier, investigation_status, created_at)
                            VALUES (?, ?, NULL, 0.0, ?, ?, ?, ?, 'CENTRAL_AI', 'PENDING', ?)
                            """,
                            (
                                c_alt_id,
                                acc,
                                datetime.now(timezone.utc).isoformat(),
                                score,
                                cls,
                                f"Part of Multi-Hop Mule Chain {cid} ({path_str}) | {reasons}",
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                        # Also elevate account score
                        conn.execute(
                            "UPDATE accounts SET risk_score = MAX(risk_score, ?), risk_band = ? WHERE account_id = ?",
                            (score, cls, acc),
                        )

            # 6. Mark transactions corresponding to alerted accounts
            conn.execute(
                """
                UPDATE transactions
                SET is_flagged = 1, risk_score = 85.0
                WHERE sender_id IN (SELECT account_id FROM fraud_alerts)
                   OR receiver_id IN (SELECT account_id FROM fraud_alerts)
                """
            )

            # Link transactions to alerts if transaction_id is null
            unlinked_alerts = conn.execute(
                "SELECT alert_id, account_id FROM fraud_alerts WHERE transaction_id IS NULL"
            ).fetchall()
            for ua in unlinked_alerts:
                t_match = conn.execute(
                    "SELECT transaction_id, amount, timestamp FROM transactions WHERE sender_id = ? OR receiver_id = ? ORDER BY timestamp DESC LIMIT 1",
                    (ua["account_id"], ua["account_id"]),
                ).fetchone()
                if t_match:
                    conn.execute(
                        "UPDATE fraud_alerts SET transaction_id = ?, amount = ?, timestamp = ? WHERE alert_id = ?",
                        (t_match["transaction_id"], float(t_match["amount"]), str(t_match["timestamp"]), ua["alert_id"]),
                    )

            conn.commit()

            # Count summary
            total_acc = conn.execute("SELECT COUNT(*) as c FROM accounts").fetchone()["c"]
            total_tx = conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"]
            total_alt = conn.execute("SELECT COUNT(*) as c FROM fraud_alerts").fetchone()["c"]
            total_chn = conn.execute("SELECT COUNT(*) as c FROM detected_chains").fetchone()["c"]

            return {
                "success": True,
                "total_accounts": total_acc,
                "total_transactions": total_tx,
                "total_alerts": total_alt,
                "total_chains": total_chn,
            }
        finally:
            conn.close()

    def get_fraud_overview(self) -> Dict[str, Any]:
        """Fetch high-level fraud operations metrics."""
        conn = get_connection()
        try:
            total_monitored_accounts = conn.execute(
                "SELECT COUNT(*) as c FROM accounts"
            ).fetchone()["c"]

            total_monitored_transactions = conn.execute(
                "SELECT COUNT(*) as c FROM transactions"
            ).fetchone()["c"]

            active_fraud_alerts = conn.execute(
                "SELECT COUNT(*) as c FROM fraud_alerts WHERE investigation_status != 'FALSE_POSITIVE'"
            ).fetchone()["c"]

            total_suspicious_accounts = conn.execute(
                "SELECT COUNT(DISTINCT account_id) as c FROM accounts WHERE risk_score >= 50.0 OR account_id IN (SELECT account_id FROM fraud_alerts)"
            ).fetchone()["c"]

            total_flagged_transactions = conn.execute(
                "SELECT COUNT(*) as c FROM transactions WHERE is_flagged = 1 OR risk_score >= 60"
            ).fetchone()["c"]

            total_flagged_value_row = conn.execute(
                "SELECT SUM(amount) as s FROM transactions WHERE is_flagged = 1 OR risk_score >= 60"
            ).fetchone()
            total_flagged_value = float(total_flagged_value_row["s"] or 0.0)

            high_risk_accounts = conn.execute(
                "SELECT COUNT(DISTINCT account_id) as c FROM accounts WHERE risk_band IN ('CRITICAL', 'HIGH')"
            ).fetchone()["c"]

            investigations_in_progress = conn.execute(
                "SELECT COUNT(*) as c FROM cases WHERE status IN ('OPEN', 'IN_PROGRESS', 'UNDER_REVIEW')"
            ).fetchone()["c"]

            pending_investigations = conn.execute(
                "SELECT COUNT(*) as c FROM fraud_alerts WHERE investigation_status = 'PENDING'"
            ).fetchone()["c"]

            confirmed_fraud_cases = conn.execute(
                "SELECT COUNT(*) as c FROM cases WHERE status = 'CONFIRMED' OR case_id IN (SELECT DISTINCT case_id FROM case_entities WHERE entity_type='ACCOUNT' AND entity_id IN (SELECT account_id FROM fraud_alerts WHERE investigation_status='CONFIRMED_MULE'))"
            ).fetchone()["c"]

            confirmed_mules = conn.execute(
                "SELECT COUNT(DISTINCT account_id) as c FROM fraud_alerts WHERE investigation_status = 'CONFIRMED_MULE'"
            ).fetchone()["c"]

            recent_alerts_rows = conn.execute(
                """
                SELECT a.alert_id, a.account_id, acc.bank_id, a.transaction_id, a.amount, 
                       a.timestamp, a.risk_score, a.risk_classification, a.detection_reason, 
                       a.source_tier, a.investigation_status
                FROM fraud_alerts a
                LEFT JOIN accounts acc ON a.account_id = acc.account_id
                ORDER BY a.risk_score DESC, a.timestamp DESC
                LIMIT 10
                """
            ).fetchall()
            recent_alerts = [dict(r) for r in recent_alerts_rows]

            recent_tx_rows = conn.execute(
                """
                SELECT t.transaction_id, t.sender_id, s.bank_id as sender_bank, 
                       t.receiver_id, r.bank_id as receiver_bank, t.amount, 
                       t.timestamp, t.channel, t.risk_score, t.is_flagged
                FROM transactions t
                LEFT JOIN accounts s ON t.sender_id = s.account_id
                LEFT JOIN accounts r ON t.receiver_id = r.account_id
                ORDER BY t.risk_score DESC, t.timestamp DESC
                LIMIT 8
                """
            ).fetchall()
            recent_suspicious_transactions = [dict(r) for r in recent_tx_rows]

            # Cross-bank activity summary
            cross_bank_rows = conn.execute(
                """
                SELECT s.bank_id as sender_bank, r.bank_id as receiver_bank, 
                       COUNT(*) as tx_count, SUM(t.amount) as total_volume,
                       AVG(t.risk_score) as avg_risk
                FROM transactions t
                JOIN accounts s ON t.sender_id = s.account_id
                JOIN accounts r ON t.receiver_id = r.account_id
                WHERE s.bank_id != r.bank_id
                GROUP BY s.bank_id, r.bank_id
                ORDER BY total_volume DESC
                """
            ).fetchall()
            cross_bank_activity = [dict(r) for r in cross_bank_rows]

            # Top risk distribution
            dist_rows = conn.execute(
                """
                SELECT risk_classification, COUNT(*) as cnt
                FROM fraud_alerts
                GROUP BY risk_classification
                """
            ).fetchall()
            risk_distribution = {r["risk_classification"]: r["cnt"] for r in dist_rows}

            # Fraud trends (daily / hourly bucket)
            trend_rows = conn.execute(
                """
                SELECT SUBSTR(timestamp, 1, 10) as day, 
                       COUNT(*) as total_alerts,
                       SUM(CASE WHEN risk_classification IN ('CRITICAL', 'HIGH') THEN 1 ELSE 0 END) as severe_alerts,
                       SUM(amount) as alert_volume
                FROM fraud_alerts
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
                """
            ).fetchall()
            fraud_trends = [dict(r) for r in trend_rows]

            # Latest investigation actions
            audit_recent = conn.execute(
                """
                SELECT log_id, case_id, account_id, action, notes, performed_by, timestamp
                FROM investigation_audit_log
                ORDER BY timestamp DESC
                LIMIT 6
                """
            ).fetchall()
            latest_investigation_activity = [dict(r) for r in audit_recent]

            return {
                "total_monitored_accounts": total_monitored_accounts,
                "total_monitored_transactions": total_monitored_transactions,
                "active_fraud_alerts": active_fraud_alerts,
                "total_suspicious_accounts": total_suspicious_accounts,
                "total_flagged_transactions": total_flagged_transactions,
                "total_flagged_value": total_flagged_value,
                "high_risk_accounts": high_risk_accounts,
                "investigations_in_progress": investigations_in_progress,
                "pending_investigations": pending_investigations,
                "confirmed_fraud_cases": max(confirmed_fraud_cases, confirmed_mules),
                "confirmed_mules": confirmed_mules,
                "recent_alerts": recent_alerts,
                "recent_suspicious_transactions": recent_suspicious_transactions,
                "risk_distribution": risk_distribution,
                "cross_bank_activity": cross_bank_activity,
                "fraud_trends": fraud_trends,
                "latest_investigation_activity": latest_investigation_activity,
            }
        finally:
            conn.close()

    def get_fraud_alerts(
        self,
        risk_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        search_account: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Fetch alert feed with optional filters."""
        conn = get_connection()
        try:
            query = """
                SELECT a.alert_id, a.account_id, acc.bank_id, a.transaction_id, a.amount, a.timestamp, 
                       a.risk_score, a.risk_classification, a.detection_reason, a.source_tier, a.investigation_status
                FROM fraud_alerts a
                LEFT JOIN accounts acc ON a.account_id = acc.account_id
                WHERE 1=1
            """
            params = []
            if risk_filter and risk_filter != "ALL":
                query += " AND a.risk_classification = ?"
                params.append(risk_filter)

            if status_filter and status_filter != "ALL":
                query += " AND a.investigation_status = ?"
                params.append(status_filter)

            if search_account:
                query += " AND (a.account_id LIKE ? OR a.transaction_id LIKE ? OR a.alert_id LIKE ?)"
                params.append(f"%{search_account}%")
                params.append(f"%{search_account}%")
                params.append(f"%{search_account}%")

            query += " ORDER BY a.risk_score DESC, a.timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_accounts_list(
        self,
        role_filter: Optional[str] = None,
        risk_filter: Optional[str] = None,
        bank_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 150,
    ) -> List[Dict[str, Any]]:
        """Query searchable accounts with summaries for the Suspicious Accounts view."""
        conn = get_connection()
        try:
            query = """
                SELECT a.account_id, a.bank_id, a.account_role, a.city_code, a.opened_on,
                       a.current_balance, a.risk_score, a.risk_band, a.status,
                       (SELECT COUNT(*) FROM transactions WHERE sender_id = a.account_id OR receiver_id = a.account_id) as total_tx_count,
                       (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE receiver_id = a.account_id) as total_in_volume,
                       (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE sender_id = a.account_id) as total_out_volume,
                       (SELECT COUNT(*) FROM fraud_alerts WHERE account_id = a.account_id) as alert_count
                FROM accounts a
                WHERE 1=1
            """
            params = []
            if role_filter and role_filter != "ALL":
                query += " AND a.account_role = ?"
                params.append(role_filter)
            if risk_filter and risk_filter != "ALL":
                query += " AND a.risk_band = ?"
                params.append(risk_filter)
            if bank_filter and bank_filter != "ALL":
                query += " AND a.bank_id = ?"
                params.append(bank_filter)
            if search_query:
                query += " AND (a.account_id LIKE ? OR a.city_code LIKE ?)"
                params.append(f"%{search_query}%")
                params.append(f"%{search_query}%")

            query += " ORDER BY a.risk_score DESC, alert_count DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_transactions_list(
        self,
        min_amount: Optional[float] = None,
        channel_filter: Optional[str] = None,
        risk_filter: Optional[str] = None,
        sender_bank: Optional[str] = None,
        receiver_bank: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Query transactions with sorting, filtering, and pagination for Transactions Explorer."""
        conn = get_connection()
        try:
            where_clauses = ["1=1"]
            params = []

            if min_amount and min_amount > 0:
                where_clauses.append("t.amount >= ?")
                params.append(min_amount)
            if channel_filter and channel_filter != "ALL":
                where_clauses.append("t.channel = ?")
                params.append(channel_filter)
            if risk_filter == "HIGH_CRITICAL":
                where_clauses.append("t.risk_score >= 60")
            elif risk_filter == "FLAGGED_ONLY":
                where_clauses.append("t.is_flagged = 1")
            elif risk_filter == "BENIGN":
                where_clauses.append("t.risk_score < 40")
            if sender_bank and sender_bank != "ALL":
                where_clauses.append("s.bank_id = ?")
                params.append(sender_bank)
            if receiver_bank and receiver_bank != "ALL":
                where_clauses.append("r.bank_id = ?")
                params.append(receiver_bank)
            if search_query:
                where_clauses.append("(t.transaction_id LIKE ? OR t.sender_id LIKE ? OR t.receiver_id LIKE ?)")
                params.append(f"%{search_query}%")
                params.append(f"%{search_query}%")
                params.append(f"%{search_query}%")

            where_sql = " AND ".join(where_clauses)

            count_query = f"""
                SELECT COUNT(*) as c
                FROM transactions t
                LEFT JOIN accounts s ON t.sender_id = s.account_id
                LEFT JOIN accounts r ON t.receiver_id = r.account_id
                WHERE {where_sql}
            """
            total_records = conn.execute(count_query, params).fetchone()["c"]

            data_query = f"""
                SELECT t.transaction_id, t.sender_id, s.bank_id as sender_bank, 
                       t.receiver_id, r.bank_id as receiver_bank, t.amount, 
                       t.timestamp, t.channel, t.ground_truth_label, t.is_flagged, t.risk_score,
                       (SELECT COUNT(*) FROM fraud_alerts WHERE transaction_id = t.transaction_id) as alert_count
                FROM transactions t
                LEFT JOIN accounts s ON t.sender_id = s.account_id
                LEFT JOIN accounts r ON t.receiver_id = r.account_id
                WHERE {where_sql}
                ORDER BY t.risk_score DESC, t.timestamp DESC
                LIMIT ? OFFSET ?
            """
            data_params = list(params) + [limit, offset]
            rows = conn.execute(data_query, data_params).fetchall()

            return {
                "total": total_records,
                "records": [dict(r) for r in rows],
                "limit": limit,
                "offset": offset,
            }
        finally:
            conn.close()

    def get_transaction_network_graph(
        self,
        focus_account: Optional[str] = None,
        min_amount: float = 0.0,
        max_hops: int = 2,
        high_risk_only: bool = False,
    ) -> Dict[str, Any]:
        """Build interactive transaction graph data structure for network visualization."""
        conn = get_connection()
        try:
            if focus_account and focus_account.strip():
                # Get ego-network nodes
                center = focus_account.strip()
                # 1 hop
                h1_rows = conn.execute(
                    "SELECT sender_id, receiver_id FROM transactions WHERE sender_id = ? OR receiver_id = ?",
                    (center, center)
                ).fetchall()
                node_ids = {center}
                for u, v in h1_rows:
                    node_ids.add(u)
                    node_ids.add(v)
                
                # 2 hops if requested
                if max_hops >= 2 and len(node_ids) < 60:
                    placeholders = ",".join(["?"] * len(node_ids))
                    h2_rows = conn.execute(
                        f"SELECT sender_id, receiver_id FROM transactions WHERE sender_id IN ({placeholders}) OR receiver_id IN ({placeholders})",
                        list(node_ids) * 2
                    ).fetchall()
                    for u, v in h2_rows:
                        node_ids.add(u)
                        node_ids.add(v)
            else:
                # Top high risk and chain nodes
                if high_risk_only:
                    top_accs = conn.execute(
                        "SELECT account_id FROM accounts WHERE risk_score >= 60 OR account_role LIKE '%MULE%' LIMIT 35"
                    ).fetchall()
                else:
                    top_accs = conn.execute(
                        "SELECT account_id FROM accounts WHERE risk_score >= 40 OR account_id IN (SELECT sender_id FROM transactions WHERE is_flagged = 1) LIMIT 45"
                    ).fetchall()
                node_ids = {r[0] for r in top_accs}

            if not node_ids:
                node_ids = {"ACC_076", "ACC_077", "ACC_078", "ACC_049"}

            # Fetch nodes metadata
            placeholders = ",".join(["?"] * len(node_ids))
            nodes_rows = conn.execute(
                f"""SELECT account_id, bank_id, account_role, risk_score, risk_band, status, current_balance,
                           (SELECT COUNT(*) FROM fraud_alerts WHERE account_id = accounts.account_id) as alert_count
                    FROM accounts WHERE account_id IN ({placeholders})""",
                list(node_ids)
            ).fetchall()

            # Fetch edges between these nodes
            edges_rows = conn.execute(
                f"""SELECT t.transaction_id, t.sender_id, t.receiver_id, t.amount, t.timestamp, 
                           t.channel, t.is_flagged, t.risk_score
                    FROM transactions t
                    WHERE t.sender_id IN ({placeholders}) AND t.receiver_id IN ({placeholders})
                      AND t.amount >= ?
                    ORDER BY t.timestamp ASC""",
                list(node_ids) + list(node_ids) + [min_amount]
            ).fetchall()

            nodes_data = []
            for r in nodes_rows:
                d = dict(r)
                role = d.get("account_role", "RETAIL")
                if "MULE" in role:
                    node_type = "MULE_ACCOUNT"
                elif "SMURF" in role:
                    node_type = "SMURF_HUB"
                elif "MERCHANT" in role or "VENDOR" in role:
                    node_type = "COMMERCIAL_HUB"
                elif "EMPLOYER" in role or "CORPORATE" in role:
                    node_type = "PAYROLL_ORIGIN"
                else:
                    node_type = "RETAIL_ACCOUNT"
                d["node_type"] = node_type
                nodes_data.append(d)

            edges_data = [dict(r) for r in edges_rows]

            return {
                "nodes": nodes_data,
                "edges": edges_data,
                "node_count": len(nodes_data),
                "edge_count": len(edges_data),
            }
        finally:
            conn.close()

    def get_kill_chain_graph(self, selected_chain_id: Optional[str] = None) -> Dict[str, Any]:
        """Construct the multi-layered Kill Chain investigation graph model."""
        conn = get_connection()
        try:
            chains_rows = conn.execute(
                "SELECT chain_id, path_str, hop_count, duration_minutes, retention_pct, risk_score, classification, reason_codes FROM detected_chains ORDER BY risk_score DESC"
            ).fetchall()
            chains = [dict(r) for r in chains_rows]

            active_chain_id = selected_chain_id or (chains[0]["chain_id"] if chains else "CHAIN_001")
            chain_match = next((c for c in chains if c["chain_id"] == active_chain_id), (chains[0] if chains else None))

            nodes = []
            edges = []

            if chain_match and chain_match.get("path_str"):
                path_accs = [a.strip() for a in chain_match["path_str"].split("->") if a.strip()]
                total_hops = len(path_accs)

                for idx, acc_id in enumerate(path_accs):
                    acc_row = conn.execute(
                        "SELECT account_id, bank_id, account_role, risk_score, risk_band, status, current_balance FROM accounts WHERE account_id = ?",
                        (acc_id,)
                    ).fetchone()
                    acc_info = dict(acc_row) if acc_row else {"account_id": acc_id, "bank_id": "UNKNOWN", "risk_score": 75.0, "risk_band": "HIGH"}

                    # Assign kill chain stage
                    if idx == 0:
                        kc_stage = "PLACEMENT"
                        stage_label = "Phishing / Fraud Origin (Placement)"
                        color = "#3B82F6" # Blue
                    elif idx == total_hops - 1:
                        kc_stage = "EXTRACTION"
                        stage_label = "Final Collector / Exit Point"
                        color = "#EF4444" # Red
                    elif idx == 1:
                        kc_stage = "COMPROMISED_RELAY"
                        stage_label = "Primary Compromised Account"
                        color = "#F59E0B" # Amber
                    else:
                        kc_stage = "LAYERING_MULE"
                        stage_label = f"Layering Mule Node (Hop {idx})"
                        color = "#00FF66" # Neon green

                    alerts = [dict(r) for r in conn.execute("SELECT alert_id, risk_score, detection_reason FROM fraud_alerts WHERE account_id = ?", (acc_id,)).fetchall()]

                    nodes.append({
                        "id": acc_id,
                        "label": acc_id,
                        "bank": acc_info.get("bank_id", "BANK"),
                        "risk_score": acc_info.get("risk_score", 70.0),
                        "risk_band": acc_info.get("risk_band", "HIGH"),
                        "status": acc_info.get("status", "ACTIVE"),
                        "kc_stage": kc_stage,
                        "stage_label": stage_label,
                        "color": color,
                        "hop_index": idx,
                        "alerts": alerts,
                    })

                # Create sequential edges
                for i in range(len(path_accs) - 1):
                    u = path_accs[i]
                    v = path_accs[i + 1]
                    tx_match = conn.execute(
                        "SELECT transaction_id, amount, timestamp, channel FROM transactions WHERE sender_id = ? AND receiver_id = ? ORDER BY timestamp DESC LIMIT 1",
                        (u, v)
                    ).fetchone()
                    tx_info = dict(tx_match) if tx_match else {
                        "transaction_id": f"TX_RELAY_{u}_{v}",
                        "amount": 95000.0 - (i * 2500.0),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "channel": "IMPS"
                    }
                    edges.append({
                        "id": f"edge_{u}_{v}",
                        "source": u,
                        "target": v,
                        "amount": float(tx_info["amount"]),
                        "channel": tx_info["channel"],
                        "timestamp": tx_info["timestamp"],
                        "tx_id": tx_info["transaction_id"],
                    })

            return {
                "active_chain": chain_match,
                "all_chains": chains,
                "nodes": nodes,
                "edges": edges,
            }
        finally:
            conn.close()

    def get_cases_list(self) -> List[Dict[str, Any]]:
        """Fetch all persistent investigation cases with linked entities and notes count."""
        conn = get_connection()
        try:
            cases_rows = conn.execute(
                """
                SELECT c.case_id, c.title, c.priority, c.status, c.assigned_to, c.created_at, c.updated_at, c.summary,
                       (SELECT COUNT(*) FROM case_entities WHERE case_id = c.case_id) as entity_count,
                       (SELECT COUNT(*) FROM case_notes WHERE case_id = c.case_id) as notes_count
                FROM cases c
                ORDER BY CASE c.priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, c.updated_at DESC
                """
            ).fetchall()
            return [dict(r) for r in cases_rows]
        finally:
            conn.close()

    def get_case_details(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Fetch complete details of an investigation case including linked entities and notes."""
        conn = get_connection()
        try:
            case_row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
            if not case_row:
                return None
            case = dict(case_row)

            entities = [
                dict(r) for r in conn.execute(
                    "SELECT link_id, entity_type, entity_id, notes, linked_at FROM case_entities WHERE case_id = ? ORDER BY linked_at ASC",
                    (case_id,)
                ).fetchall()
            ]

            notes = [
                dict(r) for r in conn.execute(
                    "SELECT note_id, author, note_text, created_at FROM case_notes WHERE case_id = ? ORDER BY created_at DESC",
                    (case_id,)
                ).fetchall()
            ]

            return {
                "case": case,
                "entities": entities,
                "notes": notes,
            }
        finally:
            conn.close()

    def create_case(self, title: str, priority: str, assigned_to: str, summary: str) -> Dict[str, Any]:
        """Create a new persistent investigation case."""
        conn = get_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        case_id = f"CASE-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"
        try:
            conn.execute(
                """
                INSERT INTO cases (case_id, title, priority, status, assigned_to, created_at, updated_at, summary)
                VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?)
                """,
                (case_id, title, priority, assigned_to, now_str, now_str, summary)
            )
            conn.execute(
                """
                INSERT INTO investigation_audit_log (case_id, account_id, action, notes, performed_by, timestamp)
                VALUES (?, 'CASE_SYSTEM', 'INVESTIGATION_CASE_CREATED', ?, ?, ?)
                """,
                (case_id, f"Case created with priority {priority}", assigned_to, now_str)
            )
            conn.commit()
            return {"success": True, "case_id": case_id}
        finally:
            conn.close()

    def add_case_note(self, case_id: str, author: str, note_text: str) -> bool:
        """Add persistent note to case."""
        conn = get_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                "INSERT INTO case_notes (case_id, author, note_text, created_at) VALUES (?, ?, ?, ?)",
                (case_id, author, note_text, now_str)
            )
            conn.execute(
                "UPDATE cases SET updated_at = ? WHERE case_id = ?",
                (now_str, case_id)
            )
            conn.execute(
                """
                INSERT INTO investigation_audit_log (case_id, account_id, action, notes, performed_by, timestamp)
                VALUES (?, 'CASE_NOTE', 'NOTE_ADDED', ?, ?, ?)
                """,
                (case_id, f"Note: {note_text[:50]}...", author, now_str)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def link_case_entity(self, case_id: str, entity_type: str, entity_id: str, notes: str) -> bool:
        """Link an account, transaction, or alert to an active case."""
        conn = get_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """
                INSERT INTO case_entities (case_id, entity_type, entity_id, notes, linked_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (case_id, entity_type, entity_id, notes, now_str)
            )
            conn.execute("UPDATE cases SET updated_at = ? WHERE case_id = ?", (now_str, case_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def update_case_status(self, case_id: str, new_status: str, author: str, justification: str) -> bool:
        """Update case disposition status."""
        conn = get_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                "UPDATE cases SET status = ?, updated_at = ? WHERE case_id = ?",
                (new_status, now_str, case_id)
            )
            conn.execute(
                """
                INSERT INTO investigation_audit_log (case_id, account_id, action, notes, performed_by, timestamp)
                VALUES (?, 'CASE_STATUS', ?, ?, ?, ?)
                """,
                (case_id, f"CASE_STATUS_UPDATED_TO_{new_status}", justification, author, now_str)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_suspicious_account_details(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Fetch 360-degree forensic profile for a specific account."""
        conn = get_connection()
        try:
            account_row = conn.execute(
                "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
            ).fetchone()
            if not account_row:
                return None

            account = dict(account_row)

            # Inbound txns
            in_rows = conn.execute(
                "SELECT * FROM transactions WHERE receiver_id = ? ORDER BY timestamp DESC LIMIT 50",
                (account_id,),
            ).fetchall()
            inflows = [dict(r) for r in in_rows]

            # Outbound txns
            out_rows = conn.execute(
                "SELECT * FROM transactions WHERE sender_id = ? ORDER BY timestamp DESC LIMIT 50",
                (account_id,),
            ).fetchall()
            outflows = [dict(r) for r in out_rows]

            total_in = sum(float(tx["amount"]) for tx in inflows)
            total_out = sum(float(tx["amount"]) for tx in outflows)
            pass_through_ratio = min(total_out, total_in) / total_in if total_in > 0 else 0.0

            # Alerts for this account
            alert_rows = conn.execute(
                "SELECT * FROM fraud_alerts WHERE account_id = ? ORDER BY risk_score DESC",
                (account_id,),
            ).fetchall()
            alerts = [dict(r) for r in alert_rows]

            # Chains involving this account
            chain_rows = conn.execute(
                "SELECT * FROM detected_chains WHERE path_str LIKE ? ORDER BY risk_score DESC",
                (f"%{account_id}%",),
            ).fetchall()
            chains = [dict(r) for r in chain_rows]

            # Connected Counterparties
            counterparties = list(
                set([tx["sender_id"] for tx in inflows] + [tx["receiver_id"] for tx in outflows])
            )

            # Investigation history
            audit_rows = conn.execute(
                "SELECT * FROM investigation_audit_log WHERE account_id = ? ORDER BY timestamp DESC",
                (account_id,),
            ).fetchall()
            audit_trail = [dict(r) for r in audit_rows]

            return {
                "account": account,
                "total_inflow": total_in,
                "total_outflow": total_out,
                "net_flow": total_in - total_out,
                "inflow_count": len(inflows),
                "outflow_count": len(outflows),
                "pass_through_ratio": round(pass_through_ratio, 3),
                "avg_transaction_amount": round((total_in + total_out) / max(1, len(inflows) + len(outflows)), 2),
                "inbound_transactions": inflows,
                "outbound_transactions": outflows,
                "alerts": alerts,
                "chains": chains,
                "counterparties": counterparties,
                "audit_trail": audit_trail,
            }
        finally:
            conn.close()

    def get_transaction_investigation(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed transaction forensic record."""
        conn = get_connection()
        try:
            tx_row = conn.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
            ).fetchone()
            if not tx_row:
                return None

            tx = dict(tx_row)
            sender = dict(
                conn.execute(
                    "SELECT * FROM accounts WHERE account_id = ?", (tx["sender_id"],)
                ).fetchone()
                or {}
            )
            receiver = dict(
                conn.execute(
                    "SELECT * FROM accounts WHERE account_id = ?", (tx["receiver_id"],)
                ).fetchone()
                or {}
            )

            alerts = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM fraud_alerts WHERE transaction_id = ? OR account_id IN (?, ?)",
                    (transaction_id, tx["sender_id"], tx["receiver_id"]),
                ).fetchall()
            ]

            # Associated chains
            chains = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM detected_chains WHERE path_str LIKE ? AND path_str LIKE ?",
                    (f"%{tx['sender_id']}%", f"%{tx['receiver_id']}%"),
                ).fetchall()
            ]

            return {
                "transaction": tx,
                "sender": sender,
                "receiver": receiver,
                "alerts": alerts,
                "chains": chains,
            }
        finally:
            conn.close()

    def update_investigation_status(
        self,
        alert_id: str,
        account_id: str,
        new_status: str,
        notes: str,
        analyst_name: str = "Senior Fraud Analyst",
    ) -> Dict[str, Any]:
        """Update case disposition and record audit trail in SQLite."""
        conn = get_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        try:
            # 1. Update alert
            conn.execute(
                "UPDATE fraud_alerts SET investigation_status = ? WHERE alert_id = ?",
                (new_status, alert_id),
            )

            # 2. Update account status if confirmed
            if new_status == "CONFIRMED_MULE":
                conn.execute(
                    "UPDATE accounts SET status = 'FROZEN_MULE_CONFIRMED' WHERE account_id = ?",
                    (account_id,),
                )
            elif new_status == "FALSE_POSITIVE":
                conn.execute(
                    "UPDATE accounts SET status = 'ACTIVE_CLEARED_FP', risk_score = 10.0 WHERE account_id = ?",
                    (account_id,),
                )

            # 3. Create or update investigation case
            case_id = f"CASE_{account_id}"
            conn.execute(
                """
                INSERT OR REPLACE INTO investigation_cases
                (case_id, account_id, alert_id, status, notes, updated_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM investigation_cases WHERE case_id = ?), ?))
                """,
                (case_id, account_id, alert_id, new_status, notes, now_str, case_id, now_str),
            )

            # 4. Insert audit log
            conn.execute(
                """
                INSERT INTO investigation_audit_log
                (case_id, account_id, action, notes, performed_by, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (case_id, account_id, f"DISPOSITION_CHANGED_TO_{new_status}", notes, analyst_name, now_str),
            )

            conn.commit()
            return {"success": True, "alert_id": alert_id, "new_status": new_status, "timestamp": now_str}
        finally:
            conn.close()

    def submit_instant_transaction(
        self, sender_id: str, receiver_id: str, amount: float, channel: str = "TRANSFER"
    ) -> Dict[str, Any]:
        """Execute real-time transaction detection and persist result."""
        engine = InstantDetectionEngine()
        return engine.evaluate_transaction(
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            channel=channel,
            persist=True,
        )


__all__ = ["FraudInvestigationService"]
