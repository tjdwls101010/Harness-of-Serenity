CREATE TABLE tweets (
    id TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    content TEXT,
    tickers TEXT DEFAULT '[]',
    media TEXT DEFAULT '[]'
);

INSERT INTO tweets (id, user, type, created_at, content, tickers, media) VALUES
    ('tweet-1', 'analyst', 'post', '2026-01-01T00:00:00Z', 'method note', '[]', '["__MEDIA_BASE__/alpha.png", "__MEDIA_BASE__/alpha.png"]'),
    ('tweet-2', 'analyst', 'reply', '2026-01-02T00:00:00Z', 'reply note', '[]', '["__MEDIA_BASE__/bravo.jpg"]'),
    ('tweet-3', 'analyst', 'subscriber', '2026-01-03T00:00:00Z', 'subscriber note', '[]', '[]'),
    ('tweet-4', 'analyst', 'post', '2026-01-04T00:00:00Z', 'missing media field', '[]', NULL);
