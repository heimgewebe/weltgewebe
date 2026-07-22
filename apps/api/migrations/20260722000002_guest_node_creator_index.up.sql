-- Guest ownership is queried on every bounded create and during account exit.
-- Keep the current JSONB compatibility model, but make the security-relevant
-- creator lookup indexable until ownership moves to a native column.
CREATE INDEX IF NOT EXISTS domain_nodes_created_by_account_id_idx
    ON domain_nodes ((payload ->> 'created_by_account_id'))
    WHERE payload ? 'created_by_account_id';
