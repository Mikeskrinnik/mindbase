-- Mindbase schema v0
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Sources: where context comes from
CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('cli', 'webhook', 'mcp', 'browser', 'mobile', 'voice', 'manual')),
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Raw context fragments (immutable event log)
CREATE TABLE fragments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(id),
    external_id TEXT,
    content_type TEXT NOT NULL DEFAULT 'text/plain',
    raw_content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'done', 'failed')),
    UNIQUE (source_id, external_id)
);

CREATE INDEX idx_fragments_status ON fragments(processing_status) WHERE processing_status != 'done';
CREATE INDEX idx_fragments_captured_at ON fragments(captured_at DESC);
CREATE INDEX idx_fragments_metadata ON fragments USING gin(metadata);

-- Structured context entries (processed, searchable)
CREATE TABLE entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fragment_id UUID REFERENCES fragments(id) ON DELETE SET NULL,
    title TEXT,
    summary TEXT,
    body TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    entities JSONB NOT NULL DEFAULT '[]',
    importance REAL NOT NULL DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
    embedding vector(1536),
    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_entries_embedding ON entries USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_entries_tags ON entries USING gin(tags);
CREATE INDEX idx_entries_valid_from ON entries(valid_from DESC);
CREATE INDEX idx_entries_body_trgm ON entries USING gin(body gin_trgm_ops);

-- Relationships between entries
CREATE TABLE entry_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_entry_id UUID NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    to_entry_id UUID NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    relation TEXT NOT NULL CHECK (relation IN ('related', 'follows', 'contradicts', 'supports', 'part_of')),
    weight REAL NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (from_entry_id, to_entry_id, relation)
);

-- Attachments (stored in S3/MinIO)
CREATE TABLE attachments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fragment_id UUID REFERENCES fragments(id) ON DELETE CASCADE,
    entry_id UUID REFERENCES entries(id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Processing dead letter queue
CREATE TABLE failed_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fragment_id UUID REFERENCES fragments(id),
    error TEXT NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Default sources
INSERT INTO sources (name, kind) VALUES
    ('cli', 'cli'),
    ('webhook', 'webhook'),
    ('mcp', 'mcp'),
    ('manual', 'manual');
