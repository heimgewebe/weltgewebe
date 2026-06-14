DROP INDEX IF EXISTS domain_accounts_email_normalized_unique;
ALTER TABLE domain_accounts
    DROP CONSTRAINT IF EXISTS domain_accounts_email_not_empty_after_trim;
