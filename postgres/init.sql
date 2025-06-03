CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    category TEXT, -- Log type specific (LogEngine etc...)
    message TEXT,
    timestamp TIMESTAMP, 
    line_number INT,
    hash TEXT UNIQUE,
    status TEXT DEFAULT 'open' -- 'open', 'closed', 'resolved', etc.
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    issue_id INT REFERENCES issues(id),
    severity TEXT NOT NULL, -- 'error' or 'warning'
    category TEXT,
    message TEXT,
    timestamp TIMESTAMP,
    line_number INT,
    hash TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS error_traceback (
    id SERIAL PRIMARY KEY,
    error_id INT REFERENCES events(id),
    message TEXT NOT NULL,
    line_number INT,
    hash TEXT UNIQUE
);
