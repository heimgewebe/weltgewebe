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
-- lookup index stays non-unique for login; only the after-trim-empty check
-- constraint and this normalized partial unique index are added.

-- Preflight: fail loudly (no data output, no mutation) if existing rows would
-- violate the new invariants. The repo-local runtime audit observed an empty
-- domain_accounts table, but other databases may already hold legacy rows from
-- earlier backfills or tests. Cleanup must be done deliberately, never silently
-- by this migration.
DO $$
DECLARE
    duplicate_group_count bigint;
    empty_after_trim_count bigint;
BEGIN
    SELECT count(*) INTO duplicate_group_count
    FROM (
        SELECT lower(btrim(email)) AS email_key
        FROM domain_accounts
        WHERE email IS NOT NULL
          AND btrim(email) <> ''
        GROUP BY lower(btrim(email))
        HAVING count(*) > 1
    ) groups;

    SELECT count(*) INTO empty_after_trim_count
    FROM domain_accounts
    WHERE email IS NOT NULL
      AND btrim(email) = '';

    IF duplicate_group_count > 0 THEN
        RAISE EXCEPTION
            'domain_accounts has % normalized non-empty email duplicate group(s); run the account email audit/cleanup before applying domain_accounts_email_normalized_unique',
            duplicate_group_count;
    END IF;

    IF empty_after_trim_count > 0 THEN
        RAISE EXCEPTION
            'domain_accounts has % after-trim-empty email value(s); normalize them to NULL before applying domain_accounts_email_normalized_unique',
            empty_after_trim_count;
    END IF;
END $$;

-- Reject after-trim-empty emails at the storage layer: a non-NULL email must be
-- non-empty after trimming. NULL stays allowed (= "no email").
ALTER TABLE domain_accounts
    ADD CONSTRAINT domain_accounts_email_not_empty_after_trim
    CHECK (email IS NULL OR btrim(email) <> '');

CREATE UNIQUE INDEX domain_accounts_email_normalized_unique
    ON domain_accounts (lower(btrim(email)))
    WHERE email IS NOT NULL AND btrim(email) <> '';
