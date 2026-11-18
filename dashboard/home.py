"""Mule Buster — Cybercrime Fraud Investigation Command Center.

A dark financial cybercrime investigation platform providing real-time
fraud surveillance, alert management, 360-degree account forensics,
transaction relationship network mapping, live multi-hop kill chain graphs,
risk analysis, and case workflows.
"""

from datetime import datetime, timezone
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components

from services.investigation_service import FraudInvestigationService


# ── Design System & CSS ───────────────────────────────────────────
_DARK_CYBER_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Inter:wght@300;400;500;600;700&display=swap');

/* Main Canvas Reset */
[data-testid="stAppViewContainer"] {
    background-color: #070B0E !important;
    color: #E6EDF3 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
[data-testid="stSidebar"] {
    background-color: #0A1016 !important;
    border-right: 1px solid #13222D !important;
}
[data-testid="stHeader"] {
    background-color: #070B0E !important;
    border-bottom: 1px solid #13222D !important;
}
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 98% !important;
}

/* Scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #0A1016;
}
::-webkit-scrollbar-thumb {
    background: #1B2F3D;
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: #00FF66;
}

/* Command Center Header */
.cyber-header {
    background: linear-gradient(135deg, #0C151D 0%, #081017 100%);
    border: 1px solid #162938;
    border-left: 3px solid #00FF66;
    border-radius: 8px;
    padding: 1rem 1.4rem;
    margin-bottom: 1.2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}
.cyber-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
.cyber-title span.glow-dot {
    display: inline-block;
    width: 9px;
    height: 9px;
    background: #00FF66;
    border-radius: 50%;
    box-shadow: 0 0 10px #00FF66;
    animation: pulse-dot 2s infinite ease-in-out;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 0.8; transform: scale(1); }
    50% { opacity: 0.3; transform: scale(0.85); }
}
.cyber-subtitle {
    font-size: 0.76rem;
    color: #7D8B99;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 2px;
}

/* Metric / Telemetry Cards */
.cyber-kpi-card {
    background: #0C141C;
    border: 1px solid #162938;
    border-radius: 6px;
    padding: 0.9rem 1rem;
    text-align: left;
    position: relative;
    overflow: hidden;
    transition: all 0.2s ease-in-out;
}
.cyber-kpi-card:hover {
    border-color: #00FF66;
    box-shadow: 0 0 14px rgba(0, 255, 102, 0.12);
}
.cyber-kpi-card .kpi-label {
    font-size: 0.72rem;
    color: #7D8B99;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}
.cyber-kpi-card .kpi-value {
    font-size: 1.75rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #FFFFFF;
    margin: 0.2rem 0;
}
.cyber-kpi-card .kpi-sub {
    font-size: 0.7rem;
    color: #4E6170;
}

/* Section Title Headers */
.cyber-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #162938;
    padding-bottom: 0.4rem;
    margin: 1.2rem 0 0.8rem 0;
}
.cyber-section-title {
    font-size: 1rem;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.01em;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.cyber-section-badge {
    background: #11202C;
    border: 1px solid #1D3A4F;
    color: #00FF66;
    font-size: 0.68rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    padding: 2px 8px;
    border-radius: 4px;
}

/* Status Badges */
.badge-critical {
    background: rgba(255, 59, 48, 0.15);
    border: 1px solid #FF3B30;
    color: #FF5E55;
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 0.72rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}
.badge-high {
    background: rgba(255, 149, 0, 0.15);
    border: 1px solid #FF9500;
    color: #FFB340;
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 0.72rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}
.badge-elevated {
    background: rgba(0, 168, 255, 0.15);
    border: 1px solid #00A8FF;
    color: #40BFFF;
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 0.72rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}
.badge-low {
    background: rgba(0, 255, 102, 0.12);
    border: 1px solid #00FF66;
    color: #00FF66;
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 0.72rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}

/* Container Boxes */
.cyber-panel {
    background: #0C141C;
    border: 1px solid #162938;
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 0.9rem;
}

/* Monospace Helpers */
.mono-font {
    font-family: 'JetBrains Mono', monospace;
}

/* Streamlit Widget Overrides */
div[data-baseweb="select"] > div {
    background-color: #0A1118 !important;
    border-color: #193144 !important;
    color: #E6EDF3 !important;
}
.stTextInput > div > div > input {
    background-color: #0A1118 !important;
    border-color: #193144 !important;
    color: #E6EDF3 !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.stButton > button {
    background-color: #0E1B26 !important;
    color: #00FF66 !important;
    border: 1px solid #1B394E !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background-color: #00FF66 !important;
    color: #070B0E !important;
    border-color: #00FF66 !important;
    box-shadow: 0 0 12px rgba(0, 255, 102, 0.35) !important;
}
button[kind="primary"] {
    background-color: #00FF66 !important;
    color: #070B0E !important;
    border-color: #00FF66 !important;
    font-weight: 700 !important;
}
button[kind="primary"]:hover {
    background-color: #1aff75 !important;
    box-shadow: 0 0 16px rgba(0, 255, 102, 0.5) !important;
}
</style>
"""


def _get_service() -> FraudInvestigationService:
    """Retrieve or initialize the singleton FraudInvestigationService."""
    if "fraud_service" not in st.session_state:
        srv = FraudInvestigationService()
        ov = srv.get_fraud_overview()
        if ov["total_monitored_accounts"] == 0:
            srv.sync_database_from_pipeline()
        st.session_state["fraud_service"] = srv
    return st.session_state["fraud_service"]


def main():
    """Main application entry point."""
    st.set_page_config(
        page_title="Mule Buster — Financial Cybercrime Command Center",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_DARK_CYBER_CSS, unsafe_allow_html=True)
    service = _get_service()

    # ── Sidebar Navigation ─────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 0.6rem 0.2rem 1rem 0.2rem;">
                <div style="display:flex; align-items:center; gap:0.6rem;">
                    <div style="font-size:1.6rem;">🛡️</div>
                    <div>
                        <div style="font-size:1.15rem; font-weight:800; color:#FFFFFF; letter-spacing:0.04em;">MULE BUSTER</div>
                        <div style="font-size:0.68rem; color:#00FF66; font-family:'JetBrains Mono', monospace;">AML FRAUD COMMAND CENTER</div>
                    </div>
                </div>
            </div>
            <div style="border-bottom: 1px solid #162938; margin-bottom: 0.8rem;"></div>
            """,
            unsafe_allow_html=True,
        )

        nav_options = [
            "1. Fraud Overview",
            "2. Fraud Alerts",
            "3. Suspicious Accounts",
            "4. Transactions",
            "5. Transaction Network",
            "6. Kill Chain Graph",
            "7. Risk Analysis",
            "8. Investigation Management",
        ]

        # Sync URL query params or session state for page navigation
        if "active_nav" not in st.session_state:
            st.session_state["active_nav"] = nav_options[0]

        selected_page = st.radio(
            "INVESTIGATOR OPERATIONS",
            nav_options,
            index=nav_options.index(st.session_state["active_nav"]) if st.session_state["active_nav"] in nav_options else 0,
            label_visibility="visible",
        )
        st.session_state["active_nav"] = selected_page

        st.markdown(
            """
            <div style="margin-top: 1.5rem; padding: 0.8rem; background: #0A1118; border: 1px solid #142838; border-radius: 4px;">
                <div style="font-size:0.68rem; color:#7D8B99; text-transform:uppercase; font-family:'JetBrains Mono'; margin-bottom:4px;">
                    OPERATOR SESSION
                </div>
                <div style="font-size:0.82rem; font-weight:600; color:#FFFFFF;">Special Agent Miller</div>
                <div style="font-size:0.72rem; color:#00FF66; font-family:'JetBrains Mono';">Consortium Surveillance: LIVE</div>
                <div style="font-size:0.68rem; color:#4E6170; margin-top:4px;">Node: AXIS/HDFC/ICICI/SBI</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Sync Ledger Database", use_container_width=True):
            with st.spinner("Re-syncing AI pipeline outputs into SQLite..."):
                service.sync_database_from_pipeline()
                st.success("Ledger & AI pipeline synced!")
                st.rerun()

    # ── Command Center Header ──────────────────────────────────────
    st.markdown(
        """
        <div class="cyber-header">
            <div>
                <div class="cyber-title">
                    <span class="glow-dot"></span>
                    MULE BUSTER // FINANCIAL CYBERCRIME INVESTIGATION PLATFORM
                </div>
                <div class="cyber-subtitle">
                    Cross-Bank Money Mule Detection · Multi-Hop Kill Chain Analysis · Time-Respecting Ledger Intelligence
                </div>
            </div>
            <div style="display:flex; gap:8px;">
                <span class="badge-low">ENGINE: RUNNING</span>
                <span class="badge-elevated">CONSORTIUM: 5 NODES</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Page Router ────────────────────────────────────────────────
    if selected_page == "1. Fraud Overview":
        _render_fraud_overview(service)
    elif selected_page == "2. Fraud Alerts":
        _render_fraud_alerts(service)
    elif selected_page == "3. Suspicious Accounts":
        _render_suspicious_accounts(service)
    elif selected_page == "4. Transactions":
        _render_transactions_explorer(service)
    elif selected_page == "5. Transaction Network":
        _render_transaction_network(service)
    elif selected_page == "6. Kill Chain Graph":
        _render_kill_chain_graph(service)
    elif selected_page == "7. Risk Analysis":
        _render_risk_analysis(service)
    elif selected_page == "8. Investigation Management":
        _render_investigation_management(service)


# ──────────────────────────────────────────────────────────────────
# 1. FRAUD OVERVIEW
# ──────────────────────────────────────────────────────────────────
def _render_fraud_overview(service: FraudInvestigationService):
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">📊 FRAUD OPERATIONS &amp; TELEMETRY OVERVIEW</div>
            <div class="cyber-section-badge">REAL-TIME CONSORTIUM FEED</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ov = service.get_fraud_overview()

    # Row 1: Key Performance Indicators
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.markdown(
            f"""
            <div class="cyber-kpi-card">
                <div class="kpi-label">Monitored Accounts</div>
                <div class="kpi-value">{ov['total_monitored_accounts']}</div>
                <div class="kpi-sub">Across 5 Banks</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""
            <div class="cyber-kpi-card">
                <div class="kpi-label">Monitored Txns</div>
                <div class="kpi-value">{ov['total_monitored_transactions']}</div>
                <div class="kpi-sub">Time-Indexed Ledger</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""
            <div class="cyber-kpi-card">
                <div class="kpi-label">Active Alerts</div>
                <div class="kpi-value" style="color:#FFB340;">{ov['active_fraud_alerts']}</div>
                <div class="kpi-sub">Requires Review</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"""
            <div class="cyber-kpi-card">
                <div class="kpi-label">High-Risk Accounts</div>
                <div class="kpi-value" style="color:#FF5E55;">{ov['high_risk_accounts']}</div>
                <div class="kpi-sub">Score ≥ 60.0</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k5:
        st.markdown(
            f"""
            <div class="cyber-kpi-card">
                <div class="kpi-label">Active Inquiries</div>
                <div class="kpi-value" style="color:#00A8FF;">{ov['investigations_in_progress']}</div>
                <div class="kpi-sub">Assigned Cases</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k6:
        st.markdown(
            f"""
            <div class="cyber-kpi-card">
                <div class="kpi-label">Confirmed Mules</div>
                <div class="kpi-value" style="color:#00FF66;">{ov['confirmed_mules']}</div>
                <div class="kpi-sub">SAR Escalations</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Row 2: Charts (Cross-Bank Flow & Risk Distribution)
    col_chart1, col_chart2 = st.columns([1.6, 1.4])
    with col_chart1:
        st.markdown(
            """
            <div class="cyber-panel">
                <div style="font-size:0.85rem; font-weight:700; color:#FFFFFF; margin-bottom:8px; font-family:'JetBrains Mono';">
                    CROSS-BANK SUSPICIOUS INTER-ENTITY VALUE FLOW (₹)
                </div>
            """,
            unsafe_allow_html=True,
        )
        if ov["cross_bank_activity"]:
            df_cb = pd.DataFrame(ov["cross_bank_activity"]).head(7)
            df_cb["corridor"] = df_cb["sender_bank"] + " ➔ " + df_cb["receiver_bank"]
            fig_bar = px.bar(
                df_cb,
                x="corridor",
                y="total_volume",
                color="avg_risk",
                color_continuous_scale=["#00A8FF", "#FFB340", "#FF3B30"],
                labels={"total_volume": "Volume (₹)", "corridor": "Bank Corridor", "avg_risk": "Avg Risk"},
            )
            fig_bar.update_layout(
                paper_bgcolor="#0C141C",
                plot_bgcolor="#0A1118",
                font_color="#7D8B99",
                height=280,
                margin=dict(l=10, r=10, t=10, b=10),
                coloraxis_colorbar=dict(title="Risk", len=0.8),
            )
            fig_bar.update_xaxes(showgrid=False, tickangle=-25)
            fig_bar.update_yaxes(showgrid=True, gridcolor="#162938")
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No cross-bank activity recorded yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_chart2:
        st.markdown(
            """
            <div class="cyber-panel">
                <div style="font-size:0.85rem; font-weight:700; color:#FFFFFF; margin-bottom:8px; font-family:'JetBrains Mono';">
                    RISK SEVERITY CLASSIFICATION BREAKDOWN
                </div>
            """,
            unsafe_allow_html=True,
        )
        dist = ov.get("risk_distribution", {})
        if dist:
            fig_pie = px.pie(
                names=list(dist.keys()),
                values=list(dist.values()),
                color=list(dist.keys()),
                color_discrete_map={
                    "CRITICAL": "#FF3B30",
                    "HIGH": "#FF9500",
                    "ELEVATED": "#00A8FF",
                    "LOW": "#00FF66",
                },
                hole=0.55,
            )
            fig_pie.update_layout(
                paper_bgcolor="#0C141C",
                plot_bgcolor="#0C141C",
                font_color="#7D8B99",
                height=280,
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Row 3: Recent Suspicious Transactions & Latest Investigation Log
    col_t1, col_t2 = st.columns([1.6, 1.4])
    with col_t1:
        st.markdown(
            """
            <div class="cyber-section-header">
                <div class="cyber-section-title">⚡ RECENTLY DETECTED SUSPICIOUS TRANSFERS</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if ov["recent_suspicious_transactions"]:
            df_stx = pd.DataFrame(ov["recent_suspicious_transactions"])[
                ["transaction_id", "sender_id", "sender_bank", "receiver_id", "receiver_bank", "amount", "risk_score", "timestamp"]
            ]
            st.dataframe(
                df_stx,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "amount": st.column_config.NumberColumn("Amount (₹)", format="₹%.2f"),
                    "risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%.0f"),
                },
            )
        else:
            st.info("No suspicious transactions detected.")

    with col_t2:
        st.markdown(
            """
            <div class="cyber-section-header">
                <div class="cyber-section-title">📜 RECENT CASE ACTIONS &amp; AUDIT TRAIL</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if ov["latest_investigation_activity"]:
            df_act = pd.DataFrame(ov["latest_investigation_activity"])[
                ["case_id", "action", "performed_by", "timestamp"]
            ]
            st.dataframe(df_act, use_container_width=True, hide_index=True)
        else:
            st.info("No prior analyst actions logged.")


# ──────────────────────────────────────────────────────────────────
# 2. FRAUD ALERTS
# ──────────────────────────────────────────────────────────────────
def _render_fraud_alerts(service: FraudInvestigationService):
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">🚨 ACTIVE FRAUD ALERTS &amp; TRIAGE MANAGEMENT</div>
            <div class="cyber-section-badge">CENTRAL AI &amp; BANK AI ANOMALY QUEUE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Filters
    c_f1, c_f2, c_f3 = st.columns([1, 1, 2])
    with c_f1:
        risk_filter = st.selectbox("Filter Risk Severity", ["ALL", "CRITICAL", "HIGH", "ELEVATED", "LOW"])
    with c_f2:
        status_filter = st.selectbox("Investigation Status", ["ALL", "PENDING", "UNDER_REVIEW", "CONFIRMED_MULE", "FALSE_POSITIVE"])
    with c_f3:
        search_query = st.text_input("Search Alert ID, Account ID, or Txn ID", placeholder="e.g. ALT_... or ACC_076")

    alerts = service.get_fraud_alerts(
        risk_filter=risk_filter,
        status_filter=status_filter,
        search_account=search_query.strip() if search_query else None,
        limit=250,
    )

    st.caption(f"Displaying {len(alerts)} alerts matching active filter parameters.")

    if alerts:
        df_al = pd.DataFrame(alerts)
        st.dataframe(
            df_al[[
                "alert_id", "account_id", "bank_id", "transaction_id", "amount", 
                "risk_score", "risk_classification", "detection_reason", "source_tier", "investigation_status"
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "amount": st.column_config.NumberColumn("Amount (₹)", format="₹%.2f"),
                "risk_score": st.column_config.ProgressColumn("Risk Score", min_value=0, max_value=100, format="%.1f"),
            },
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="cyber-section-header">
                <div class="cyber-section-title">⚖️ INVESTIGATOR TRIAGE WORKBENCH</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Select alert to triage
        alert_ids = [a["alert_id"] for a in alerts]
        selected_aid = st.selectbox("Select Alert to Triage:", alert_ids)
        target_alert = next(a for a in alerts if a["alert_id"] == selected_aid)

        c_d1, c_d2 = st.columns([1.2, 1.8])
        with c_d1:
            st.markdown(
                f"""
                <div class="cyber-panel">
                    <div style="font-size:0.75rem; color:#7D8B99; font-family:'JetBrains Mono';">ALERT METADATA</div>
                    <div style="font-size:1.1rem; font-weight:700; color:#FFFFFF; margin:4px 0;">{target_alert['alert_id']}</div>
                    <div style="font-size:0.8rem; color:#A4B3C2;">
                        <b>Subject Account:</b> <span class="mono-font">{target_alert['account_id']}</span><br>
                        <b>Bank Node:</b> {target_alert.get('bank_id', 'UNKNOWN')}<br>
                        <b>Associated Txn:</b> <span class="mono-font">{target_alert.get('transaction_id') or 'N/A'}</span><br>
                        <b>Amount at Risk:</b> ₹{float(target_alert.get('amount') or 0):,.2f}<br>
                        <b>Source Detection Tier:</b> {target_alert['source_tier']}<br>
                        <b>Current Status:</b> <b>{target_alert['investigation_status']}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c_d2:
            st.markdown(
                f"""
                <div class="cyber-panel">
                    <div style="font-size:0.75rem; color:#7D8B99; font-family:'JetBrains Mono';">DETECTION REASON &amp; EVIDENCE</div>
                    <div style="color:#FFB340; font-size:0.85rem; margin-top:6px; line-height:1.4;">
                        {target_alert['detection_reason']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Action form
        with st.form(f"triage_form_{selected_aid}"):
            c_act1, c_act2, c_act3 = st.columns([1.2, 2.2, 1])
            with c_act1:
                new_status = st.selectbox(
                    "Update Status",
                    ["UNDER_REVIEW", "CONFIRMED_MULE", "FALSE_POSITIVE", "PENDING"],
                    index=["UNDER_REVIEW", "CONFIRMED_MULE", "FALSE_POSITIVE", "PENDING"].index(
                        target_alert["investigation_status"] if target_alert["investigation_status"] in ["UNDER_REVIEW", "CONFIRMED_MULE", "FALSE_POSITIVE", "PENDING"] else "PENDING"
                    )
                )
            with c_act2:
                notes = st.text_input("Investigator Notes & Disposition Rationale:", value=f"Triaged alert {selected_aid} - evidence verified.")
            with c_act3:
                st.write("&nbsp;")
                btn_save = st.form_submit_button("💾 Save Disposition", type="primary", use_container_width=True)

            if btn_save:
                service.update_investigation_status(
                    alert_id=target_alert["alert_id"],
                    account_id=target_alert["account_id"],
                    new_status=new_status,
                    notes=notes,
                    analyst_name="Special Agent Miller",
                )
                st.success(f"Alert {selected_aid} updated to {new_status} and persisted to SQLite audit log!")
                st.rerun()
    else:
        st.info("No alerts found matching your filter criteria.")


# ──────────────────────────────────────────────────────────────────
# 3. SUSPICIOUS ACCOUNTS
# ──────────────────────────────────────────────────────────────────
def _render_suspicious_accounts(service: FraudInvestigationService):
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">👤 SUSPICIOUS ACCOUNT DIRECTORY &amp; 360° FORENSICS</div>
            <div class="cyber-section-badge">ACCOUNT LEVEL ANOMALY INTELLIGENCE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        risk_f = st.selectbox("Risk Band", ["ALL", "CRITICAL", "HIGH", "ELEVATED", "LOW"])
    with f2:
        role_f = st.selectbox("Role Archetype", ["ALL", "MULE_CHAIN", "DORMANT_MULE", "SMURF_HUB", "MERCHANT", "CUSTOMER"])
    with f3:
        bank_f = st.selectbox("Bank Node", ["ALL", "HDFC_BANK", "ICICI_BANK", "SBI_COMMERCIAL", "AXIS_BANK", "BANK_SIM_01"])
    with f4:
        search_q = st.text_input("Search Account ID or City", placeholder="e.g. ACC_076")

    accounts = service.get_accounts_list(
        role_filter=role_f,
        risk_filter=risk_f,
        bank_filter=bank_f,
        search_query=search_q.strip() if search_q else None,
        limit=100,
    )

    st.caption(f"Loaded {len(accounts)} accounts from persistent database.")

    if accounts:
        df_acc = pd.DataFrame(accounts)
        st.dataframe(
            df_acc[[
                "account_id", "bank_id", "account_role", "city_code", "opened_on", 
                "risk_score", "risk_band", "total_tx_count", "total_in_volume", "total_out_volume", "alert_count", "status"
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "risk_score": st.column_config.ProgressColumn("Risk Score", min_value=0, max_value=100, format="%.1f"),
                "total_in_volume": st.column_config.NumberColumn("Inflow (₹)", format="₹%.0f"),
                "total_out_volume": st.column_config.NumberColumn("Outflow (₹)", format="₹%.0f"),
            },
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="cyber-section-header">
                <div class="cyber-section-title">🔎 360° ACCOUNT FORENSIC DOSSIER</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        target_acc_id = st.selectbox("Select Account ID for Deep Investigation:", [a["account_id"] for a in accounts])
        details = service.get_suspicious_account_details(target_acc_id)

        if details:
            acc = details["account"]
            rb = acc.get("risk_band", "LOW")
            badge_class = (
                "badge-critical" if rb == "CRITICAL"
                else "badge-high" if rb == "HIGH"
                else "badge-elevated" if rb == "ELEVATED"
                else "badge-low"
            )

            # Profile Bar
            st.markdown(
                f"""
                <div class="cyber-panel">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-size:1.3rem; font-weight:800; font-family:'JetBrains Mono'; color:#FFFFFF;">{acc['account_id']}</span>
                            <span style="margin-left:10px; color:#7D8B99;">Bank: <b>{acc.get('bank_id')}</b> | Role: <b>{acc.get('account_role')}</b> | City: <b>{acc.get('city_code')}</b></span>
                        </div>
                        <div>
                            <span class="{badge_class}">RISK: {acc.get('risk_score', 0):.1f} ({rb})</span>
                            <span class="badge-elevated" style="margin-left:8px;">STATUS: {acc.get('status')}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 4 Metric Cards
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(
                    f"""
                    <div class="cyber-kpi-card">
                        <div class="kpi-label">Total Inbound</div>
                        <div class="kpi-value" style="color:#00FF66;">₹{details['total_inflow']:,.0f}</div>
                        <div class="kpi-sub">{details['inflow_count']} Funding Transfers</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    f"""
                    <div class="cyber-kpi-card">
                        <div class="kpi-label">Total Outbound</div>
                        <div class="kpi-value" style="color:#FF5E55;">₹{details['total_outflow']:,.0f}</div>
                        <div class="kpi-sub">{details['outflow_count']} Dispersal Transfers</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with m3:
                st.markdown(
                    f"""
                    <div class="cyber-kpi-card">
                        <div class="kpi-label">Pass-Through Depletion</div>
                        <div class="kpi-value" style="color:#FFB340;">{details['pass_through_ratio'] * 100:.1f}%</div>
                        <div class="kpi-sub">Rapid Skimming Ratio</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with m4:
                st.markdown(
                    f"""
                    <div class="cyber-kpi-card">
                        <div class="kpi-label">Avg Transaction</div>
                        <div class="kpi-value">₹{details['avg_transaction_amount']:,.0f}</div>
                        <div class="kpi-sub">Transfer Velocity</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Alerts & Chains Tabs
            tab_alerts, tab_tx, tab_audit = st.tabs(["Active Alerts & Chains", "Full Inbound / Outbound History", "Investigator Audit Log"])
            with tab_alerts:
                if details["alerts"]:
                    st.write("**Associated Fraud Alerts:**")
                    st.dataframe(pd.DataFrame(details["alerts"]), use_container_width=True, hide_index=True)
                if details["chains"]:
                    st.write("**Associated Money Mule Chains:**")
                    st.dataframe(pd.DataFrame(details["chains"]), use_container_width=True, hide_index=True)
                if not details["alerts"] and not details["chains"]:
                    st.info("No active alerts or chains for this account.")

            with tab_tx:
                st.write("**Inbound (Credits):**")
                if details["inbound_transactions"]:
                    st.dataframe(pd.DataFrame(details["inbound_transactions"]), use_container_width=True, hide_index=True)
                st.write("**Outbound (Debits):**")
                if details["outbound_transactions"]:
                    st.dataframe(pd.DataFrame(details["outbound_transactions"]), use_container_width=True, hide_index=True)

            with tab_audit:
                if details["audit_trail"]:
                    st.dataframe(pd.DataFrame(details["audit_trail"]), use_container_width=True, hide_index=True)
                else:
                    st.info("No prior analyst actions logged for this account.")


# ──────────────────────────────────────────────────────────────────
# 4. TRANSACTIONS
# ──────────────────────────────────────────────────────────────────
def _render_transactions_explorer(service: FraudInvestigationService):
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">💸 TIME-INDEXED TRANSACTION EXPLORER</div>
            <div class="cyber-section-badge">INTER-BANK LEDGER RECORD FACTS</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        risk_filter = st.selectbox("Risk Filter", ["ALL", "HIGH_CRITICAL", "FLAGGED_ONLY", "BENIGN"])
    with c2:
        channel_filter = st.selectbox("Channel", ["ALL", "IMPS_TRANSFER", "UPI_TRANSFER", "NEFT_SETTLEMENT", "RTGS_B2B", "TRANSFER"])
    with c3:
        min_amt = st.number_input("Minimum Amount (₹)", min_value=0.0, value=0.0, step=5000.0)
    with c4:
        search_q = st.text_input("Search Txn ID or Account", placeholder="e.g. TXN_0170 or ACC_076")

    # Pagination
    limit = 50
    page_num = st.number_input("Page Number", min_value=1, value=1, step=1)
    offset = (page_num - 1) * limit

    data = service.get_transactions_list(
        min_amount=min_amt,
        channel_filter=channel_filter,
        risk_filter=risk_filter,
        search_query=search_q.strip() if search_q else None,
        limit=limit,
        offset=offset,
    )

    total_matches = data["total"]
    records = data["records"]
    st.caption(f"Showing page {page_num} ({len(records)} of {total_matches} total matching ledger records)")

    if records:
        df_tx = pd.DataFrame(records)
        st.dataframe(
            df_tx[[
                "transaction_id", "sender_id", "sender_bank", "receiver_id", "receiver_bank", 
                "amount", "timestamp", "channel", "is_flagged", "risk_score", "alert_count"
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "amount": st.column_config.NumberColumn("Amount (₹)", format="₹%.2f"),
                "risk_score": st.column_config.ProgressColumn("Risk Score", min_value=0, max_value=100, format="%.0f"),
            },
        )

        st.markdown("<br>", unsafe_allow_html=True)
        # Deep inspection of a single transaction
        st.markdown(
            """
            <div class="cyber-section-header">
                <div class="cyber-section-title">🔬 INDIVIDUAL TRANSFER FORENSICS</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_tx = st.selectbox("Select Transaction to Inspect:", [r["transaction_id"] for r in records])
        tx_details = service.get_transaction_forensics(selected_tx)

        if tx_details:
            tx = tx_details["transaction"]
            s = tx_details["sender"]
            r = tx_details["receiver"]

            col_flow = st.columns([1.5, 0.5, 1.5])
            with col_flow[0]:
                st.markdown(
                    f"""
                    <div class="cyber-panel">
                        <div style="font-size:0.72rem; color:#7D8B99; font-family:'JetBrains Mono';">ORIGINATING SENDER</div>
                        <div style="font-size:1.1rem; font-weight:700; color:#FFFFFF; margin:4px 0;" class="mono-font">{s.get('account_id', tx['sender_id'])}</div>
                        <div style="font-size:0.8rem; color:#A4B3C2;">
                            Bank: <b>{s.get('bank_id', 'UNKNOWN')}</b><br>
                            Role: <b>{s.get('account_role', 'RETAIL')}</b><br>
                            Risk Band: <b>{s.get('risk_band', 'LOW')}</b> ({s.get('risk_score', 0):.1f})
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col_flow[1]:
                st.markdown(
                    f"""
                    <div style="text-align:center; padding-top:1.8rem;">
                        <span style="font-size:1.4rem; color:#00FF66;">➔</span><br>
                        <span style="font-size:0.75rem; color:#FFFFFF; font-weight:700; font-family:'JetBrains Mono';">₹{tx['amount']:,.0f}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col_flow[2]:
                st.markdown(
                    f"""
                    <div class="cyber-panel">
                        <div style="font-size:0.72rem; color:#7D8B99; font-family:'JetBrains Mono';">DESTINATION RECEIVER</div>
                        <div style="font-size:1.1rem; font-weight:700; color:#FFFFFF; margin:4px 0;" class="mono-font">{r.get('account_id', tx['receiver_id'])}</div>
                        <div style="font-size:0.8rem; color:#A4B3C2;">
                            Bank: <b>{r.get('bank_id', 'UNKNOWN')}</b><br>
                            Role: <b>{r.get('account_role', 'RETAIL')}</b><br>
                            Risk Band: <b>{r.get('risk_band', 'LOW')}</b> ({r.get('risk_score', 0):.1f})
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            if tx_details["alerts"]:
                st.write("**Associated Alerts for this Transfer or Counterparties:**")
                st.dataframe(pd.DataFrame(tx_details["alerts"]), use_container_width=True, hide_index=True)
    else:
        st.info("No transactions match the selected filter parameters.")


# ──────────────────────────────────────────────────────────────────
# 5. TRANSACTION NETWORK
# ──────────────────────────────────────────────────────────────────
def _render_transaction_network(service: FraudInvestigationService):
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">🌐 CROSS-BANK TRANSACTION RELATIONSHIP NETWORK</div>
            <div class="cyber-section-badge">INTER-ACCOUNT GRAPH TOPOLOGY</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        focus_acc = st.text_input("Focus Account (Ego-Network Center)", value="ACC_076", placeholder="e.g. ACC_076")
    with c2:
        min_amount = st.number_input("Min Edge Transfer (₹)", min_value=0.0, value=10000.0, step=10000.0)
    with c3:
        high_risk_only = st.checkbox("High-Risk Entities Only", value=True)

    graph_data = service.get_transaction_network_graph(
        focus_account=focus_acc.strip() if focus_acc else None,
        min_amount=min_amount,
        max_hops=2,
        high_risk_only=high_risk_only,
    )

    st.caption(f"Network Topology: {graph_data['node_count']} accounts (nodes) and {graph_data['edge_count']} transfers (edges)")

    # Build Plotly Network Graph Visualization
    import networkx as nx
    G = nx.DiGraph()
    for n in graph_data["nodes"]:
        G.add_node(n["account_id"], **n)
    for e in graph_data["edges"]:
        G.add_edge(e["sender_id"], e["receiver_id"], **e)

    if len(G.nodes()) > 0:
        pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)

        # Edges trace
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=1.2, color='#1B3B4F'),
            hoverinfo='none',
            mode='lines'
        )

        # Nodes trace
        node_x = []
        node_y = []
        node_text = []
        node_color = []
        node_size = []

        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            n_data = G.nodes[node]
            score = float(n_data.get("risk_score", 0))
            role = n_data.get("account_role", "RETAIL")
            bank = n_data.get("bank_id", "BANK")
            text = f"<b>Account:</b> {node}<br><b>Bank:</b> {bank}<br><b>Role:</b> {role}<br><b>Risk:</b> {score:.1f}"
            node_text.append(text)

            if score >= 80:
                node_color.append("#FF3B30") # Red
                node_size.append(18)
            elif score >= 60:
                node_color.append("#FF9500") # Amber
                node_size.append(15)
            elif score >= 40:
                node_color.append("#00A8FF") # Blue
                node_size.append(12)
            else:
                node_color.append("#00FF66") # Green
                node_size.append(10)

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=[n if G.nodes[n].get("risk_score", 0) >= 60 else "" for n in G.nodes()],
            textposition="top center",
            textfont=dict(family="JetBrains Mono", size=9, color="#E6EDF3"),
            hovertext=node_text,
            marker=dict(
                color=node_color,
                size=node_size,
                line=dict(width=1.5, color='#070B0E'),
            )
        )

        fig_net = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                showlegend=False,
                hovermode='closest',
                paper_bgcolor="#070B0E",
                plot_bgcolor="#070B0E",
                margin=dict(b=10, l=10, r=10, t=10),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=520,
            )
        )
        st.plotly_chart(fig_net, use_container_width=True)

        st.markdown(
            """
            <div style="display:flex; gap:15px; font-size:0.75rem; font-family:'JetBrains Mono'; color:#7D8B99;">
                <div><span style="color:#FF3B30;">●</span> Critical Risk (≥80)</div>
                <div><span style="color:#FF9500;">●</span> High Risk (60-79)</div>
                <div><span style="color:#00A8FF;">●</span> Elevated Risk (40-59)</div>
                <div><span style="color:#00FF66;">●</span> Cleared / Low Risk (&lt;40)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("No nodes found for the specified network criteria.")


# ──────────────────────────────────────────────────────────────────
# 6. KILL CHAIN GRAPH — PRIORITY INTERACTIVE VIEW
# ──────────────────────────────────────────────────────────────────
def _render_kill_chain_graph(service: FraudInvestigationService):
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">⚡ INTERACTIVE MONEY MULE KILL CHAIN GRAPH</div>
            <div class="cyber-section-badge">TEMPORAL MULTI-HOP LAYERING ATTRIBUTION</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kc_data = service.get_kill_chain_graph()
    chains = kc_data["all_chains"]

    # Chain Selector Control Bar
    c_sel, c_kpi1, c_kpi2, c_kpi3 = st.columns([1.5, 0.8, 0.8, 0.8])
    with c_sel:
        chain_opts = [c["chain_id"] for c in chains]
        selected_cid = st.selectbox("Select Detected Mule Chain:", chain_opts, index=0)
    
    # Reload with chosen chain
    if selected_cid != kc_data["active_chain"]["chain_id"]:
        kc_data = service.get_kill_chain_graph(selected_chain_id=selected_cid)

    active_c = kc_data["active_chain"]
    with c_kpi1:
        st.markdown(
            f"""
            <div class="cyber-kpi-card" style="padding:0.6rem 0.8rem;">
                <div class="kpi-label">Risk Score</div>
                <div class="kpi-value" style="font-size:1.3rem; color:#FF3B30;">{active_c['risk_score']:.1f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c_kpi2:
        st.markdown(
            f"""
            <div class="cyber-kpi-card" style="padding:0.6rem 0.8rem;">
                <div class="kpi-label">Hops Traversals</div>
                <div class="kpi-value" style="font-size:1.3rem; color:#00FF66;">{active_c['hop_count']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c_kpi3:
        st.markdown(
            f"""
            <div class="cyber-kpi-card" style="padding:0.6rem 0.8rem;">
                <div class="kpi-label">Net Retention</div>
                <div class="kpi-value" style="font-size:1.3rem; color:#FFB340;">{active_c['retention_pct']:.1f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div style="background:#0A1118; border:1px solid #142838; border-radius:4px; padding:0.6rem 1rem; margin-bottom:1rem; font-family:'JetBrains Mono'; font-size:0.78rem;">
            <span style="color:#00FF66; font-weight:700;">CHAIN PATHWAY:</span> <span style="color:#E6EDF3;">{active_c['path_str']}</span><br>
            <span style="color:#7D8B99;">REASON EVIDENCE:</span> <span style="color:#FFB340;">{active_c['reason_codes']}</span> | Duration: <b>{active_c['duration_minutes']:.1f} mins</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Main 2-Column Workspace: Interactive Canvas (Left) + Threat Intel Panel (Right)
    col_canvas, col_intel = st.columns([2.3, 1.2])

    with col_canvas:
        st.markdown(
            """
            <div style="font-size:0.75rem; color:#7D8B99; font-family:'JetBrains Mono'; margin-bottom:6px;">
                KILL CHAIN TOPOLOGY (CLICK A NODE OR BUTTON BELOW TO INSPECT FORENSICS)
            </div>
            """,
            unsafe_allow_html=True,
        )

        nodes = kc_data["nodes"]
        edges = kc_data["edges"]

        # Interactive SVG/HTML Kill Chain Diagram with CSS glow
        nodes_html = ""
        for i, n in enumerate(nodes):
            x = 50 + (i * 125)
            y = 120 + ((i % 2) * 50)
            n["x"] = x
            n["y"] = y
            nodes_html += f"""
            <g class="node-group" style="cursor:pointer;" onclick="selectNode('{n['id']}')">
                <circle cx="{x}" cy="{y}" r="22" fill="#0C151D" stroke="{n['color']}" stroke-width="2.5" filter="drop-shadow(0 0 8px {n['color']}44)"/>
                <text x="{x}" y="{y+4}" fill="#FFFFFF" font-size="9" font-family="'JetBrains Mono', monospace" font-weight="700" text-anchor="middle">{n['id'][-4:]}</text>
                <text x="{x}" y="{y-28}" fill="{n['color']}" font-size="8" font-family="'JetBrains Mono', monospace" font-weight="600" text-anchor="middle">{n['kc_stage']}</text>
                <text x="{x}" y="{y+34}" fill="#7D8B99" font-size="8" font-family="'Inter', sans-serif" text-anchor="middle">{n['bank'].split('_')[0]}</text>
            </g>
            """

        edges_html = ""
        for i in range(len(nodes) - 1):
            u = nodes[i]
            v = nodes[i + 1]
            edges_html += f"""
            <line x1="{u['x']}" y1="{u['y']}" x2="{v['x']}" y2="{v['y']}" stroke="#1E4532" stroke-width="3" stroke-dasharray="4,2"/>
            <circle cx="{(u['x']+v['x'])/2}" cy="{(u['y']+v['y'])/2}" r="3" fill="#00FF66"/>
            """

        canvas_svg = f"""
        <div style="background:#060A0D; border:1px solid #162938; border-radius:6px; padding:10px; width:100%; overflow-x:auto;">
            <svg width="{max(850, len(nodes)*135)}" height="230" style="display:block;">
                {edges_html}
                {nodes_html}
            </svg>
        </div>
        """
        components.html(canvas_svg, height=250, scrolling=True)

        # Node Selector buttons to update right intelligence panel
        st.write("**Inspect Node in Threat Intel Panel:**")
        b_cols = st.columns(len(nodes))
        for idx, n in enumerate(nodes):
            with b_cols[idx]:
                if st.button(f"{n['id']}", key=f"btn_node_{n['id']}", use_container_width=True):
                    st.session_state["selected_kc_node"] = n["id"]

    # Threat Intelligence Panel (Right Column)
    with col_intel:
        if "selected_kc_node" not in st.session_state:
            st.session_state["selected_kc_node"] = nodes[1]["id"] if len(nodes) > 1 else nodes[0]["id"]

        sel_node_id = st.session_state["selected_kc_node"]
        sel_node_info = next((n for n in nodes if n["id"] == sel_node_id), nodes[0])
        acc_dossier = service.get_suspicious_account_details(sel_node_id)

        st.markdown(
            f"""
            <div class="cyber-panel" style="border-left:3px solid {sel_node_info['color']};">
                <div style="font-size:0.7rem; color:#7D8B99; font-family:'JetBrains Mono'; text-transform:uppercase;">
                    THREAT INTELLIGENCE DOSSIER
                </div>
                <div style="font-size:1.2rem; font-weight:800; color:#FFFFFF; margin:3px 0;" class="mono-font">
                    {sel_node_info['id']}
                </div>
                <div style="font-size:0.75rem; color:{sel_node_info['color']}; font-weight:700; margin-bottom:8px;">
                    {sel_node_info['stage_label']}
                </div>
                <div style="border-top:1px solid #142838; padding-top:6px; font-size:0.8rem; line-height:1.5;">
                    <b>Institution:</b> {sel_node_info['bank']}<br>
                    <b>Entity Risk Score:</b> <span style="color:#FF3B30; font-weight:700;">{sel_node_info['risk_score']:.1f} ({sel_node_info['risk_band']})</span><br>
                    <b>Account Status:</b> {sel_node_info['status']}<br>
                    <b>Total Alerts:</b> {len(sel_node_info['alerts'])} active alerts
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if acc_dossier:
            st.markdown(
                f"""
                <div style="background:#0A1118; border:1px solid #142838; border-radius:4px; padding:0.8rem; font-size:0.78rem; line-height:1.4;">
                    <b>Total Inflow:</b> ₹{acc_dossier['total_inflow']:,.0f}<br>
                    <b>Total Outflow:</b> ₹{acc_dossier['total_outflow']:,.0f}<br>
                    <b>Pass-Through Rate:</b> <span style="color:#00FF66; font-weight:700;">{acc_dossier['pass_through_ratio']*100:.1f}%</span><br>
                    <b>Counterparties:</b> {len(acc_dossier['counterparties'])} connected nodes
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button("📁 Escalate to Investigation Case", use_container_width=True, type="primary"):
            st.session_state["link_account_to_case"] = sel_node_id
            st.session_state["active_nav"] = "8. Investigation Management"
            st.rerun()


# ──────────────────────────────────────────────────────────────────
# 7. RISK ANALYSIS
# ──────────────────────────────────────────────────────────────────
def _render_risk_analysis(service: FraudInvestigationService):
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">📈 COMPREHENSIVE RISK CALIBRATION &amp; ANOMALY ANALYSIS</div>
            <div class="cyber-section-badge">STATISTICAL &amp; HEURISTIC VERIFICATION</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ov = service.get_fraud_overview()
    accounts = service.get_accounts_list(limit=150)
    df_acc = pd.DataFrame(accounts)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class="cyber-panel">
                <div style="font-size:0.85rem; font-weight:700; color:#FFFFFF; margin-bottom:8px; font-family:'JetBrains Mono';">
                    ACCOUNT RISK SCORE DISTRIBUTION ACROSS POPULATION
                </div>
            """,
            unsafe_allow_html=True,
        )
        if not df_acc.empty:
            fig_hist = px.histogram(
                df_acc,
                x="risk_score",
                nbins=20,
                color="risk_band",
                color_discrete_map={
                    "CRITICAL": "#FF3B30",
                    "HIGH": "#FF9500",
                    "ELEVATED": "#00A8FF",
                    "LOW": "#00FF66",
                },
                labels={"risk_score": "Calibrated Risk Score (0-100)", "count": "Account Count"},
            )
            fig_hist.update_layout(
                paper_bgcolor="#0C141C",
                plot_bgcolor="#0A1118",
                font_color="#7D8B99",
                height=260,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            fig_hist.update_yaxes(showgrid=True, gridcolor="#162938")
            st.plotly_chart(fig_hist, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown(
            """
            <div class="cyber-panel">
                <div style="font-size:0.85rem; font-weight:700; color:#FFFFFF; margin-bottom:8px; font-family:'JetBrains Mono';">
                    INFLOW VS OUTFLOW VOLUME DISPERSION
                </div>
            """,
            unsafe_allow_html=True,
        )
        if not df_acc.empty:
            fig_scat = px.scatter(
                df_acc,
                x="total_in_volume",
                y="total_out_volume",
                color="risk_band",
                size="total_tx_count",
                hover_name="account_id",
                color_discrete_map={
                    "CRITICAL": "#FF3B30",
                    "HIGH": "#FF9500",
                    "ELEVATED": "#00A8FF",
                    "LOW": "#00FF66",
                },
                labels={"total_in_volume": "Total Inbound (₹)", "total_out_volume": "Total Outbound (₹)"},
            )
            fig_scat.update_layout(
                paper_bgcolor="#0C141C",
                plot_bgcolor="#0A1118",
                font_color="#7D8B99",
                height=260,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            fig_scat.update_yaxes(showgrid=True, gridcolor="#162938")
            fig_scat.update_xaxes(showgrid=True, gridcolor="#162938")
            st.plotly_chart(fig_scat, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">📑 TOP HIGH-RISK SUSPICIOUS ACCOUNT MOTIFS</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    high_risk_accs = [a for a in accounts if a["risk_score"] >= 60]
    if high_risk_accs:
        df_hr = pd.DataFrame(high_risk_accs)[
            ["account_id", "bank_id", "account_role", "risk_score", "risk_band", "total_in_volume", "total_out_volume", "alert_count"]
        ]
        st.dataframe(df_hr, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────────
# 8. INVESTIGATION MANAGEMENT
# ──────────────────────────────────────────────────────────────────
def _render_investigation_management(service: FraudInvestigationService):
    st.markdown(
        """
        <div class="cyber-section-header">
            <div class="cyber-section-title">📁 FRAUD CASE MANAGEMENT &amp; AUDIT TRAIL</div>
            <div class="cyber-section-badge">HUMAN-IN-THE-LOOP SAR WORKFLOW</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cases = service.get_cases_list()

    c_left, c_right = st.columns([1.6, 1.4])

    with c_left:
        st.subheader("Active Investigation Dossiers")
        if cases:
            df_cases = pd.DataFrame(cases)[
                ["case_id", "title", "priority", "status", "assigned_to", "entity_count", "notes_count", "updated_at"]
            ]
            st.dataframe(df_cases, use_container_width=True, hide_index=True)
        else:
            st.info("No cases created yet.")

        # Create New Case Expander
        with st.expander("➕ Open New Investigation Case"):
            with st.form("new_case_form"):
                c_t = st.text_input("Case Title", value="Rapid Layering Ring Review")
                c_p = st.selectbox("Priority", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
                c_a = st.text_input("Assigned Lead Investigator", value="Special Agent Miller")
                c_s = st.text_area("Initial Case Summary & Justification", value="Cross-bank transfer cluster exhibiting rapid pass-through layering.")
                submit_new = st.form_submit_button("Create Case Dossier", type="primary")

                if submit_new:
                    res = service.create_case(c_t, c_p, c_a, c_s)
                    st.success(f"Case {res['case_id']} created and persisted!")
                    st.rerun()

    with c_right:
        st.subheader("Case Details & Investigation Actions")
        if cases:
            case_ids = [c["case_id"] for c in cases]
            sel_case_id = st.selectbox("Select Case:", case_ids)
            case_pack = service.get_case_details(sel_case_id)

            if case_pack:
                case = case_pack["case"]
                st.markdown(
                    f"""
                    <div class="cyber-panel">
                        <div style="font-size:0.75rem; color:#7D8B99; font-family:'JetBrains Mono';">CASE DOSSIER</div>
                        <div style="font-size:1.15rem; font-weight:800; color:#FFFFFF; margin:4px 0;">{case['title']}</div>
                        <div style="font-size:0.8rem; color:#A4B3C2;">
                            <b>Case ID:</b> <span class="mono-font">{case['case_id']}</span> | <b>Priority:</b> <span style="color:#FF3B30;">{case['priority']}</span><br>
                            <b>Status:</b> <b>{case['status']}</b> | <b>Lead:</b> {case['assigned_to']}<br>
                            <span style="color:#7D8B99;">Summary: {case.get('summary')}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Update Status Form
                with st.form(f"status_form_{sel_case_id}"):
                    c_s1, c_s2 = st.columns([1, 2])
                    with c_s1:
                        up_status = st.selectbox(
                            "Update Case Status",
                            ["OPEN", "IN_PROGRESS", "UNDER_REVIEW", "CONFIRMED", "CLOSED_BENIGN"],
                            index=["OPEN", "IN_PROGRESS", "UNDER_REVIEW", "CONFIRMED", "CLOSED_BENIGN"].index(
                                case["status"] if case["status"] in ["OPEN", "IN_PROGRESS", "UNDER_REVIEW", "CONFIRMED", "CLOSED_BENIGN"] else "OPEN"
                            )
                        )
                    with c_s2:
                        just = st.text_input("Status Change Justification:", value="Reviewed network graph and chain conservation.")
                    btn_status = st.form_submit_button("Apply Case Disposition", use_container_width=True)

                    if btn_status:
                        service.update_case_status(sel_case_id, up_status, "Special Agent Miller", just)
                        st.success(f"Case updated to {up_status}!")
                        st.rerun()

                # Case Notes Tab & Entities
                t_notes, t_ents = st.tabs(["Case Notes & SAR Log", "Linked Entities"])
                with t_notes:
                    for n in case_pack["notes"]:
                        st.markdown(
                            f"""
                            <div style="background:#0A1118; border-left:3px solid #00FF66; padding:0.5rem 0.8rem; margin-bottom:6px; font-size:0.8rem;">
                                <b>{n['author']}</b> <span style="color:#7D8B99; font-size:0.7rem;">({n['created_at'][:19]})</span><br>
                                {n['note_text']}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Add Note
                    with st.form(f"note_form_{sel_case_id}"):
                        new_note = st.text_input("Add Case Note / SAR Evidence Entry:")
                        btn_note = st.form_submit_button("Add Note", type="primary")
                        if btn_note and new_note.strip():
                            service.add_case_note(sel_case_id, "Special Agent Miller", new_note.strip())
                            st.success("Note added and persisted!")
                            st.rerun()

                with t_ents:
                    if case_pack["entities"]:
                        st.dataframe(pd.DataFrame(case_pack["entities"]), use_container_width=True, hide_index=True)
                    else:
                        st.info("No entities linked to this case yet.")

                    # Link Entity Form
                    with st.form(f"link_form_{sel_case_id}"):
                        e_type = st.selectbox("Entity Type", ["ACCOUNT", "TRANSACTION", "ALERT", "CHAIN"])
                        e_id = st.text_input("Entity ID (e.g. ACC_076)", value=st.session_state.get("link_account_to_case", "ACC_076"))
                        e_notes = st.text_input("Link Reason", value="Identified in layering chain")
                        btn_link = st.form_submit_button("Link Entity to Case")
                        if btn_link and e_id.strip():
                            service.link_case_entity(sel_case_id, e_type, e_id.strip(), e_notes)
                            st.success(f"Linked {e_type} {e_id} to case!")
                            st.rerun()


if __name__ == "__main__":
    main()
