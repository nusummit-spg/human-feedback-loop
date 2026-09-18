-- ============================================================================
-- AMC Feedback Loop & Compliance Audit Schema
-- SQLite Implementation
-- ============================================================================
-- Usage:
--   sqlite3 compliance_audit.db < create_tables.sql
--
-- Or from within sqlite3:
--   .read create_tables.sql
-- ============================================================================


-- ---------------------------------------------------------
-- TABLE 1: audit_metadata
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_metadata (
    audit_id TEXT PRIMARY KEY,
    audit_run_timestamp TEXT NOT NULL,

    region TEXT NOT NULL CHECK (region IN ('SEBI', 'SEC', 'ESMA')),
    audit_type TEXT NOT NULL CHECK (audit_type IN ('full_corpus', 'single_fund', 'batch', 'continuous')),
    funds_audited_count INTEGER NOT NULL DEFAULT 0,
    funds_passed_count INTEGER,
    funds_with_violations_count INTEGER,

    total_rules_evaluated INTEGER NOT NULL DEFAULT 0,
    total_violations_detected INTEGER NOT NULL DEFAULT 0,
    critical_violations INTEGER DEFAULT 0,
    high_violations INTEGER DEFAULT 0,
    medium_violations INTEGER DEFAULT 0,
    low_violations INTEGER DEFAULT 0,

    audit_duration_ms INTEGER,
    avg_rule_evaluation_ms REAL,
    p95_rule_evaluation_ms REAL,
    p99_rule_evaluation_ms REAL,

    status TEXT NOT NULL DEFAULT 'started' CHECK (status IN ('started', 'in_progress', 'completed', 'failed')),
    triggered_by TEXT,
    triggering_action TEXT,
    error_message TEXT,

    overall_compliance_score REAL DEFAULT 0.0,
    compliance_trend TEXT CHECK (compliance_trend IN ('improving', 'stable', 'declining')),

    report_id TEXT UNIQUE,
    escalation_triggered BOOLEAN DEFAULT FALSE,

    evidence_pack_id TEXT UNIQUE,
    evidence_manifest_json TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived BOOLEAN DEFAULT FALSE,

    UNIQUE(audit_run_timestamp, region, audit_type)
);

CREATE INDEX IF NOT EXISTS idx_audit_region ON audit_metadata(region);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_metadata(audit_run_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_metadata(status);
CREATE INDEX IF NOT EXISTS idx_audit_escalation ON audit_metadata(escalation_triggered);
CREATE INDEX IF NOT EXISTS idx_audit_region_timestamp ON audit_metadata(region, audit_run_timestamp);


-- ---------------------------------------------------------
-- TABLE 2: violations
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS violations (
    violation_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    fund_id TEXT NOT NULL,

    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    violation_type TEXT NOT NULL CHECK (violation_type IN ('portfolio', 'governance', 'kyc', 'risk', 'reporting')),
    region TEXT NOT NULL CHECK (region IN ('SEBI', 'SEC', 'ESMA')),

    description TEXT NOT NULL,
    actual_value TEXT,
    threshold_value TEXT,
    gap_percentage REAL,

    confidence_score REAL NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    evidence_count INTEGER DEFAULT 0,

    status TEXT NOT NULL DEFAULT 'detected' CHECK (status IN ('detected', 'reviewed', 'remediated', 'closed', 'waived')),

    detected_at TEXT NOT NULL,
    reviewed_at TEXT,
    resolved_at TEXT,

    resolution_action TEXT,
    resolved_by_user_id TEXT,
    resolution_notes TEXT,

    evidence_docs_json TEXT,
    audit_trail_json TEXT,

    escalation_level INTEGER DEFAULT 0,
    escalation_triggered_at TEXT,
    escalation_path_id TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT,

    FOREIGN KEY(audit_id) REFERENCES audit_metadata(audit_id),
    UNIQUE(audit_id, rule_id, fund_id)
);

CREATE INDEX IF NOT EXISTS idx_violation_audit ON violations(audit_id);
CREATE INDEX IF NOT EXISTS idx_violation_fund ON violations(fund_id);
CREATE INDEX IF NOT EXISTS idx_violation_rule ON violations(rule_id);
CREATE INDEX IF NOT EXISTS idx_violation_region ON violations(region);
CREATE INDEX IF NOT EXISTS idx_violation_severity ON violations(severity);
CREATE INDEX IF NOT EXISTS idx_violation_status ON violations(status);
CREATE INDEX IF NOT EXISTS idx_violation_detected_at ON violations(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_violation_escalation ON violations(escalation_level);
CREATE INDEX IF NOT EXISTS idx_violation_region_severity ON violations(region, severity);
CREATE INDEX IF NOT EXISTS idx_violation_fund_status ON violations(fund_id, status);


-- ---------------------------------------------------------
-- TABLE 3: response_feedback
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS response_feedback (
    feedback_id TEXT PRIMARY KEY,
    response_id TEXT NOT NULL,
    interaction_id TEXT NOT NULL,
    session_id TEXT NOT NULL,

    turn_number INTEGER NOT NULL,
    query_text TEXT,

    actor_id TEXT,
    actor_role TEXT,

    selected_categories TEXT NOT NULL,
    feedback_text TEXT,

    answer_relevance_score INTEGER CHECK (answer_relevance_score IS NULL OR (answer_relevance_score BETWEEN 1 AND 5)),
    source_quality_score INTEGER CHECK (source_quality_score IS NULL OR (source_quality_score BETWEEN 1 AND 5)),
    completeness_score INTEGER CHECK (completeness_score IS NULL OR (completeness_score BETWEEN 1 AND 5)),

    automated_category TEXT,
    automated_confidence REAL CHECK (automated_confidence IS NULL OR (automated_confidence BETWEEN 0.0 AND 1.0)),

    client_timestamp TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    audit_id TEXT,
    violation_id TEXT,

    FOREIGN KEY(audit_id) REFERENCES audit_metadata(audit_id),
    FOREIGN KEY(violation_id) REFERENCES violations(violation_id),
    UNIQUE(response_id, actor_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_response ON response_feedback(response_id);
CREATE INDEX IF NOT EXISTS idx_feedback_session ON response_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_actor ON response_feedback(actor_id);
CREATE INDEX IF NOT EXISTS idx_feedback_actor_role ON response_feedback(actor_role);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON response_feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_audit ON response_feedback(audit_id);


-- ---------------------------------------------------------
-- TABLE 4: query_evidence
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS query_evidence (
    response_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    request_id TEXT,

    query_text TEXT NOT NULL,
    query_type TEXT,
    query_intent TEXT,

    retrieval_mode TEXT NOT NULL DEFAULT 'contextgraph',
    serving_engine TEXT,

    assembled_context_json TEXT NOT NULL,
    synthesis_output_json TEXT NOT NULL,
    graph_highlight_json TEXT,
    traditional_result_json TEXT,

    latency_ms INTEGER,
    retrieval_latency_ms INTEGER,
    synthesis_latency_ms INTEGER,
    quality_score REAL,
    confidence_level TEXT CHECK (confidence_level IN ('high', 'medium', 'low') OR confidence_level IS NULL),

    audit_id TEXT,
    linked_violations_json TEXT,

    has_feedback BOOLEAN DEFAULT FALSE,
    feedback_summary_json TEXT,

    created_at TEXT NOT NULL,
    archived BOOLEAN DEFAULT FALSE,

    FOREIGN KEY(audit_id) REFERENCES audit_metadata(audit_id)
);

CREATE INDEX IF NOT EXISTS idx_query_session ON query_evidence(session_id);
CREATE INDEX IF NOT EXISTS idx_query_latency ON query_evidence(latency_ms);
CREATE INDEX IF NOT EXISTS idx_query_confidence ON query_evidence(confidence_level);
CREATE INDEX IF NOT EXISTS idx_query_audit ON query_evidence(audit_id);
CREATE INDEX IF NOT EXISTS idx_query_has_feedback ON query_evidence(has_feedback);
CREATE INDEX IF NOT EXISTS idx_query_created_at ON query_evidence(created_at DESC);


-- ---------------------------------------------------------
-- TABLE 5: compliance_rules
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS compliance_rules (
    rule_id TEXT PRIMARY KEY,
    regulation_id TEXT,

    rule_type TEXT NOT NULL CHECK (rule_type IN ('portfolio', 'governance', 'kyc', 'risk', 'reporting')),
    region TEXT NOT NULL CHECK (region IN ('SEBI', 'SEC', 'ESMA')),
    title TEXT NOT NULL,
    description TEXT,

    condition_plain_text TEXT,
    condition_code_json TEXT,

    applicable_categories TEXT,
    exclusions_json TEXT,

    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    enforcement_level TEXT DEFAULT 'automatic',
    confidence_threshold REAL DEFAULT 0.95 CHECK (confidence_threshold >= 0.0 AND confidence_threshold <= 1.0),

    required_evidence_types TEXT,

    effective_from TEXT,
    effective_to TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    version_number INTEGER DEFAULT 1,

    regulation_section TEXT,
    document_url TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_modified_by TEXT,

    UNIQUE(rule_id, region, version_number)
);

CREATE INDEX IF NOT EXISTS idx_rule_type ON compliance_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_rule_region ON compliance_rules(region);
CREATE INDEX IF NOT EXISTS idx_rule_active ON compliance_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_rule_severity ON compliance_rules(severity);


-- ---------------------------------------------------------
-- TABLE 6: fund_schemes
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS fund_schemes (
    fund_id TEXT PRIMARY KEY,
    isin TEXT UNIQUE,

    name TEXT NOT NULL,
    fund_house TEXT NOT NULL,
    category TEXT,
    mandate TEXT,
    risk_profile TEXT,

    aum_crores REAL,
    nav_per_unit REAL,

    region TEXT NOT NULL CHECK (region IN ('SEBI', 'SEC', 'ESMA')),
    applicable_rules_json TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    UNIQUE(fund_id, region)
);

CREATE INDEX IF NOT EXISTS idx_fund_house ON fund_schemes(fund_house);
CREATE INDEX IF NOT EXISTS idx_fund_category ON fund_schemes(category);
CREATE INDEX IF NOT EXISTS idx_fund_region ON fund_schemes(region);


-- ---------------------------------------------------------
-- TABLE 7: sessions
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ended_at TEXT,

    audit_id TEXT,

    FOREIGN KEY(audit_id) REFERENCES audit_metadata(audit_id)
);

CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_session_created_at ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_audit ON sessions(audit_id);


-- ---------------------------------------------------------
-- TABLE 8: unified_evaluation_records (NEW)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS unified_evaluation_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    response_id TEXT NOT NULL,
    entry_route TEXT NOT NULL CHECK (entry_route IN ('hitl', 'automatic', 'dissatisfaction_converted')),

    feedback_ref TEXT UNIQUE,
    evidence_snapshot_ref TEXT,

    deterministic_results TEXT,
    gnn_plausibility_score REAL,
    semantic_results TEXT,
    llm_evaluation TEXT,

    adjudication_verdict TEXT NOT NULL CHECK (adjudication_verdict IN ('valid', 'partially_valid', 'invalid', 'subjective', 'insufficient_evidence')),
    adjudication_confidence REAL,

    root_cause TEXT CHECK (root_cause IN ('knowledge', 'retrieval', 'graph', 'context_engineering', 'model', 'guardrail', 'compliance', 'presentation', 'feedback_invalid')),
    severity TEXT CHECK (severity IN ('critical', 'high', 'medium', 'low')),

    lifecycle_status TEXT NOT NULL DEFAULT 'open' CHECK (lifecycle_status IN ('open', 'diagnosing', 'resolved', 'monitoring')),

    repair BOOLEAN NOT NULL DEFAULT FALSE,
    repair_target TEXT CHECK (repair_target IN ('vector', 'graph')),

    FOREIGN KEY(feedback_ref) REFERENCES response_feedback(feedback_id),
    UNIQUE(session_id, response_id),

    CHECK (
        (repair = 0 AND repair_target IS NULL)
        OR
        (repair = 1 AND repair_target IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_uer_session ON unified_evaluation_records(session_id);
CREATE INDEX IF NOT EXISTS idx_uer_response ON unified_evaluation_records(response_id);
CREATE INDEX IF NOT EXISTS idx_uer_entry_route ON unified_evaluation_records(entry_route);
CREATE INDEX IF NOT EXISTS idx_uer_root_cause ON unified_evaluation_records(root_cause);
CREATE INDEX IF NOT EXISTS idx_uer_severity ON unified_evaluation_records(severity);
CREATE INDEX IF NOT EXISTS idx_uer_repair ON unified_evaluation_records(repair);
CREATE INDEX IF NOT EXISTS idx_uer_lifecycle ON unified_evaluation_records(lifecycle_status);


-- ============================================================================
-- VERIFICATION QUERIES (run these to verify tables created successfully)
-- ============================================================================

-- List all tables
-- SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;

-- Count tables
-- SELECT COUNT(*) as total_tables FROM sqlite_master WHERE type='table';

-- Show detailed schema for each table
-- PRAGMA table_info(audit_metadata);
-- PRAGMA table_info(violations);
-- PRAGMA table_info(response_feedback);
-- PRAGMA table_info(query_evidence);
-- PRAGMA table_info(compliance_rules);
-- PRAGMA table_info(fund_schemes);
-- PRAGMA table_info(sessions);
-- PRAGMA table_info(unified_evaluation_records);

-- Show indices
-- SELECT name FROM sqlite_master WHERE type='index' ORDER BY name;
