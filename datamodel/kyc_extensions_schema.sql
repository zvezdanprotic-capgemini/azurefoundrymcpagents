-- KYC Session State Persistence and RAG Extensions
-- Run this AFTER the main salesforce_core_schema.sql
-- Dialect: PostgreSQL with pgvector extension

-- =====================
--  PGVECTOR EXTENSION
-- =====================
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================
--  KYC SESSIONS (State Persistence)
-- =====================
CREATE TABLE kyc_sessions (
    id UUID PRIMARY KEY,
    contact_id BIGINT REFERENCES contacts(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL,
    current_step VARCHAR(50) NOT NULL,
    customer_data JSONB NOT NULL DEFAULT '{}',
    step_results JSONB DEFAULT '{}',
    chat_history JSONB DEFAULT '[]',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_kyc_sessions_contact ON kyc_sessions(contact_id);
CREATE INDEX idx_kyc_sessions_status ON kyc_sessions(status);
CREATE INDEX idx_kyc_sessions_created ON kyc_sessions(created_at DESC);

-- =====================
--  POLICY DOCUMENTS (RAG Vector Store)
-- =====================
CREATE TABLE policy_documents (
    id BIGSERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    category VARCHAR(100),
    content TEXT NOT NULL,
    chunk_index INT NOT NULL DEFAULT 0,
    embedding vector(1536),  -- Azure OpenAI text-embedding-ada-002
    uploaded_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'indexed',
    error_message TEXT,
    chunk_size INT,
    total_chunks INT
);

-- Index for vector similarity search (IVFFlat)
-- Note: After inserting data, run: ANALYZE policy_documents;
CREATE INDEX idx_policy_embedding ON policy_documents 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_policy_category ON policy_documents(category);
CREATE INDEX idx_policy_filename ON policy_documents(filename);

-- =====================
--  CUSTOMER DOCUMENTS (Blob Metadata Cache)
-- =====================
CREATE TABLE customer_documents (
    id BIGSERIAL PRIMARY KEY,
    contact_id BIGINT REFERENCES contacts(id) ON DELETE CASCADE,
    blob_path VARCHAR(512) NOT NULL UNIQUE,
    document_type VARCHAR(50),
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT,
    uploaded_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    verified_at TIMESTAMP WITHOUT TIME ZONE,
    verification_status VARCHAR(50) DEFAULT 'pending'
);

CREATE INDEX idx_customer_docs_contact ON customer_documents(contact_id);
CREATE INDEX idx_customer_docs_type ON customer_documents(document_type);

-- =====================
--  HELPER VIEWS
-- =====================

-- View for KYC session summary
CREATE OR REPLACE VIEW v_kyc_session_summary AS
SELECT 
    k.id,
    k.status,
    k.current_step,
    k.created_at,
    k.updated_at,
    c.first_name || ' ' || c.last_name as customer_name,
    c.email as customer_email,
    jsonb_array_length(k.chat_history) as message_count
FROM kyc_sessions k
LEFT JOIN contacts c ON k.contact_id = c.id
ORDER BY k.updated_at DESC;

-- View for policy search (useful for debugging)
CREATE OR REPLACE VIEW v_policy_summary AS
SELECT 
    category,
    COUNT(DISTINCT filename) as file_count,
    COUNT(*) as chunk_count,
    MAX(uploaded_at) as last_updated
FROM policy_documents
GROUP BY category
ORDER BY category;

-- End of KYC extensions schema
