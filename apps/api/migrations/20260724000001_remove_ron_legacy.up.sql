DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM domain_accounts
        WHERE kind IS DISTINCT FROM 'garnrolle'
           OR private_payload ? 'ron_flag'
           OR private_payload ? 'visibility'
           OR private_payload ? 'suppress_public_pos'
    ) THEN
        RAISE EXCEPTION 'cannot remove legacy account identity fields while legacy rows remain';
    END IF;
END
$$;

ALTER TABLE domain_accounts DROP COLUMN mode;
