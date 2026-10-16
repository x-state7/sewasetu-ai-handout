
-- should Apply once after migrations 001 and 002.

CREATE TABLE IF NOT EXISTS mcp_document_claims (
    id BIGSERIAL PRIMARY KEY,
    token_hash CHAR(64) NOT NULL UNIQUE,
    mobile VARCHAR(15) NOT NULL,
    doc_path VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_at TIMESTAMPTZ,
    application_id INTEGER REFERENCES applications(id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_document_claims_mobile
    ON mcp_document_claims(mobile, created_at)
    WHERE used_at IS NULL;
