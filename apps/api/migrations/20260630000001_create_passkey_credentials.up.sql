-- AUTH-PG-002: persistence schema for registered WebAuthn / passkey credentials.
--
-- Schema-only migration. No runtime cutover in this slice: the in-memory
-- PasskeyStore remains the default and the routes are NOT switched to the
-- database here. This table exists so that registered passkeys can become
-- restart-stable once an explicit opt-in PostgreSQL passkey mode is wired up
-- (follow-up slice).
--
-- Security notes:
--   * Stored credentials are server-side WebAuthn *public* credential records
--     plus the signature counter and backup flags. They contain no private
--     key. They are nevertheless private auth data: never expose them through
--     public account projections and never log them in raw form.
--   * credential_id is the lowercase hex encoding of the raw WebAuthn
--     credential-ID bytes. It is globally unique; the PRIMARY KEY is the final
--     source of truth for duplicate-credential detection (a duplicate insert
--     maps to DuplicateCredentialId / 409-equivalent semantics at the store
--     layer).
--   * webauthn_user_id is the dedicated per-account WebAuthn user handle. It is
--     stored NOT NULL so a reload can verify a credential is still bound to the
--     account identity it was registered under (cross-restart consistency).
--
-- Foreign-key decision (deliberate, documented):
--   No FOREIGN KEY to domain_accounts(id) is declared here. This mirrors the
--   existing `sessions` table, whose account_id is also TEXT NOT NULL without a
--   FK, because accounts may still live in JSONL (domain_read_source=jsonl is
--   the default). Declaring the FK now would couple this schema to a
--   precondition that the store layer cannot guarantee on its own. The
--   integrity constraint belongs to the later opt-in PostgreSQL passkey mode,
--   which must additionally require domain_read_source=postgres and a live
--   pool so that the referenced account row is guaranteed to exist. This is an
--   explicit deferred precondition, NOT silent orphan tolerance.

CREATE TABLE passkey_credentials (
    credential_id    TEXT        PRIMARY KEY,
    account_id       TEXT        NOT NULL,
    webauthn_user_id UUID        NOT NULL,
    credential       JSONB       NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at     TIMESTAMPTZ
);

CREATE INDEX passkey_credentials_account_id ON passkey_credentials (account_id);
