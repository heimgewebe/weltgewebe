-- OPT-ARC-001 / TODO 2A: enforce normalized account-email uniqueness.
--
-- Invariant: two accounts must never persist the same normalized, non-empty
-- email. The normalized key is lower(btrim(email)). Missing (NULL) emails and
-- emails that are empty after trimming are NOT unique-relevant and are excluded
-- by the partial predicate, matching the API create policy (trim + empty => no
-- email) documented in docs/reports/domain-account-email-uniqueness-audit.md.
--
-- Normalization note: PostgreSQL lower(...) is not byte-identical to the Rust
-- to_ascii_lowercase() the in-memory AccountStore uses for non-ASCII input. This
-- divergence is documented and accepted as the DB-side policy in the audit
-- report above; this index is the durable race-safety boundary for the
-- PostgreSQL account-create write path.
--
-- The existing non-unique domain_accounts_email_lookup index (lower(email)) is
-- intentionally left in place for login/lookup; it indexes a different
-- expression and does not conflict with this unique index.
--
-- TODO 2A supersedes the Phase-B deferral of normalized account-email
-- uniqueness (see the non-unique lookup-index note in
-- 20260531000003_create_domain_accounts.up.sql) for non-empty emails only. The
-- lookup index stays non-unique for login; only this normalized partial unique
-- index is added.

CREATE UNIQUE INDEX IF NOT EXISTS domain_accounts_email_normalized_unique
    ON domain_accounts (lower(btrim(email)))
    WHERE email IS NOT NULL AND btrim(email) <> '';
