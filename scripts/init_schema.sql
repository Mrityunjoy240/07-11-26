-- PostgreSQL schema for BCREC AI
-- Run: psql -U bcrec -d bcrec -f init_schema.sql

CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR,
    title VARCHAR DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR REFERENCES conversations(id),
    role VARCHAR NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

CREATE TABLE IF NOT EXISTS student_profiles (
    student_id VARCHAR PRIMARY KEY,
    phone VARCHAR,
    name VARCHAR,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prompts (
    name VARCHAR PRIMARY KEY,
    content TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evaluation_log (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR,
    query TEXT,
    expected_behaviour TEXT,
    actual_behaviour TEXT,
    score REAL,
    failure_category VARCHAR,
    confidence REAL,
    created_at TIMESTAMP DEFAULT NOW()
);
