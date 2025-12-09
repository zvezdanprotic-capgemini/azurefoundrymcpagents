-- Migration script to update policy_documents table
-- Run this against your Postgres database

ALTER TABLE policy_documents 
ADD COLUMN IF NOT EXISTS original_filename VARCHAR(255),
ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'indexed',
ADD COLUMN IF NOT EXISTS error_message TEXT,
ADD COLUMN IF NOT EXISTS chunk_size INT,
ADD COLUMN IF NOT EXISTS total_chunks INT;

-- Update existing records
UPDATE policy_documents 
SET status = 'indexed', original_filename = filename 
WHERE status IS NULL;
