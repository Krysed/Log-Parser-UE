CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    log_entry_id TEXT, -- HASH unified hash for multiple data sources
    category TEXT, -- Log type specific (LogEngine etc...)
    severity TEXT NOT NULL, -- 'error' or 'warning'
    message TEXT,
    timestamp TIMESTAMP, 
    line_number INT,
    message_hash TEXT UNIQUE,
    status TEXT DEFAULT 'open' -- 'open' or 'closed'
);

CREATE TABLE IF NOT EXISTS error_traceback (
    id SERIAL PRIMARY KEY,
    issue_id INT REFERENCES issues(id),
    message TEXT NOT NULL,
    line_number INT,
    hash TEXT UNIQUE
);
