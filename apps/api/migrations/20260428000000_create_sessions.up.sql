CREATE TABLE sessions (
    id          TEXT        PRIMARY KEY,
    account_id  TEXT        NOT NULL,
    device_id   TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    last_active TIMESTAMPTZ NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX sessions_account_id ON sessions (account_id);
CREATE INDEX sessions_expires_at ON sessions (expires_at);
