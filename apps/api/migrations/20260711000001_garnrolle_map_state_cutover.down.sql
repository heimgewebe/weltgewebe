ALTER TABLE domain_accounts
    DROP CONSTRAINT IF EXISTS domain_accounts_radius_state_consistent,
    DROP CONSTRAINT IF EXISTS domain_accounts_map_state_location,
    DROP CONSTRAINT IF EXISTS domain_accounts_map_state_valid,
    DROP CONSTRAINT IF EXISTS domain_accounts_kind_garnrolle;

-- Rows that existed before the cutover still carry their original non-NULL
-- mode value. Preserve it so a private/verortet Garnrolle is not needlessly
-- reconstructed as RoN. Rows created after the cutover have mode=NULL and are
-- translated to the closest legacy representation.
UPDATE domain_accounts
SET kind = CASE
        WHEN COALESCE(mode, CASE WHEN map_state = 'not_on_map' THEN 'ron' ELSE 'verortet' END) = 'ron'
            THEN 'ron'
        ELSE 'garnrolle'
    END,
    mode = COALESCE(mode, CASE WHEN map_state = 'not_on_map' THEN 'ron' ELSE 'verortet' END);

ALTER TABLE domain_accounts
    ALTER COLUMN kind SET DEFAULT 'ron',
    ALTER COLUMN mode SET DEFAULT 'ron',
    ALTER COLUMN mode SET NOT NULL,
    DROP COLUMN map_state;
