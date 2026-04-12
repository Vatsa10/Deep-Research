CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    query TEXT NOT NULL,
    depth TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'running',
    report TEXT,
    distilled_summary TEXT,
    validation_json TEXT,
    fact_check_json TEXT,
    reasoning_trace_json TEXT,
    dag_trace_json TEXT,
    iterations INTEGER DEFAULT 0,
    continued_from TEXT REFERENCES sessions(id),
    template_id TEXT REFERENCES templates(id),
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS share_links (
    token TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    view_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    query_pattern TEXT NOT NULL,
    depth TEXT DEFAULT 'standard',
    domain TEXT DEFAULT 'general',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_shares_session ON share_links(session_id);
CREATE INDEX IF NOT EXISTS idx_templates_user ON templates(user_id);
