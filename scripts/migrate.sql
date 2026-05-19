-- scripts/migrate.sql
-- Run once against your Neon database to set up all required tables.
-- Requires the pgvector extension (available on all Neon plans).

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Sessions ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL,
    connector_id TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Query history ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS query_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    user_query      TEXT NOT NULL,
    generated_code  TEXT,
    code_type       TEXT CHECK (code_type IN ('sql','pandas')) DEFAULT 'sql',
    insight_text    TEXT,
    chart_spec      JSONB,
    result_preview  JSONB,
    retry_count     INT DEFAULT 0,
    latency_ms      INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_query_history_session ON query_history(session_id);

-- ── Schema embeddings (pgvector, 384-dim for MiniLM-L6-v2) ───────────────────
CREATE TABLE IF NOT EXISTS schema_embeddings (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connector_id   TEXT NOT NULL,
    table_name     TEXT NOT NULL,
    column_summary TEXT,
    embedding      vector(384),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_schema_emb_connector
    ON schema_embeddings(connector_id);
CREATE INDEX IF NOT EXISTS idx_schema_emb_hnsw
    ON schema_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── Memory embeddings (similar past queries) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS memory_embeddings (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id   TEXT NOT NULL,
    query        TEXT NOT NULL,
    insight      TEXT,
    table_names  TEXT[],
    embedding    vector(384),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memory_emb_session
    ON memory_embeddings(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_emb_hnsw
    ON memory_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── Dashboards ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dashboards (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Dashboard panels ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dashboard_panels (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       TEXT NOT NULL,
    session_id    TEXT,
    dashboard_id  UUID REFERENCES dashboards(id) ON DELETE SET NULL,
    title         TEXT NOT NULL,
    chart_spec    JSONB NOT NULL,
    query         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_panels_user ON dashboard_panels(user_id);
CREATE INDEX IF NOT EXISTS idx_panels_dashboard ON dashboard_panels(dashboard_id);
