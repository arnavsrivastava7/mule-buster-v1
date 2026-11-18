-- Mule Buster Production SQLite Schema
-- Financial Fraud & Money Mule Detection Platform

CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    bank_id TEXT NOT NULL,
    account_role TEXT,
    is_registered_merchant INTEGER DEFAULT 0,
    city_code TEXT,
    opened_on TEXT,
    opening_balance REAL DEFAULT 0.0,
    current_balance REAL DEFAULT 0.0,
    risk_score REAL DEFAULT 0.0,
    risk_band TEXT DEFAULT 'LOW',
    status TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    sender_id TEXT NOT NULL,
    receiver_id TEXT NOT NULL,
    amount REAL NOT NULL,
    timestamp TEXT NOT NULL,
    channel TEXT DEFAULT 'TRANSFER',
    ground_truth_label TEXT,
    is_flagged INTEGER DEFAULT 0,
    risk_score REAL DEFAULT 0.0,
    FOREIGN KEY (sender_id) REFERENCES accounts(account_id),
    FOREIGN KEY (receiver_id) REFERENCES accounts(account_id)
);

CREATE TABLE IF NOT EXISTS fraud_alerts (
    alert_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    transaction_id TEXT,
    amount REAL DEFAULT 0.0,
    timestamp TEXT NOT NULL,
    risk_score REAL NOT NULL,
    risk_classification TEXT NOT NULL,
    detection_reason TEXT NOT NULL,
    source_tier TEXT NOT NULL,
    investigation_status TEXT DEFAULT 'PENDING',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investigation_cases (
    case_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    alert_id TEXT,
    status TEXT DEFAULT 'PENDING',
    priority TEXT DEFAULT 'HIGH',
    assigned_to TEXT DEFAULT 'Senior Fraud Analyst',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investigation_audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT,
    account_id TEXT NOT NULL,
    action TEXT NOT NULL,
    notes TEXT,
    performed_by TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS detected_chains (
    chain_id TEXT PRIMARY KEY,
    path_str TEXT NOT NULL,
    hop_count INTEGER NOT NULL,
    duration_minutes REAL NOT NULL,
    retention_pct REAL NOT NULL,
    risk_score REAL NOT NULL,
    classification TEXT NOT NULL,
    reason_codes TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    priority TEXT DEFAULT 'HIGH',
    status TEXT DEFAULT 'OPEN',
    assigned_to TEXT DEFAULT 'Lead AML Investigator',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS case_entities (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    entity_type TEXT NOT NULL, -- 'ACCOUNT', 'TRANSACTION', 'ALERT', 'CHAIN'
    entity_id TEXT NOT NULL,
    notes TEXT,
    linked_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
);

CREATE TABLE IF NOT EXISTS case_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    author TEXT NOT NULL,
    note_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
);

CREATE INDEX IF NOT EXISTS idx_tx_sender ON transactions(sender_id);
CREATE INDEX IF NOT EXISTS idx_tx_receiver ON transactions(receiver_id);
CREATE INDEX IF NOT EXISTS idx_tx_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_account ON fraud_alerts(account_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON fraud_alerts(investigation_status);
CREATE INDEX IF NOT EXISTS idx_alerts_score ON fraud_alerts(risk_score);
