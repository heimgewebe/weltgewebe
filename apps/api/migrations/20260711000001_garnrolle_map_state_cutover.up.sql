-- Canonicalise account identity to one Garnrolle per account while retaining
-- the deprecated mode column as a nullable rollback bridge.
ALTER TABLE domain_accounts
    ADD COLUMN map_state TEXT;

UPDATE domain_accounts
SET map_state = CASE
    WHEN kind = 'ron'
      OR mode = 'ron'
      OR COALESCE(private_payload->>'ron_flag', 'false') = 'true'
      OR private_payload->>'visibility' = 'private'
      OR COALESCE(private_payload->>'suppress_public_pos', 'false') = 'true'
      OR location_lat IS NULL
      OR location_lon IS NULL
        THEN 'not_on_map'
    WHEN radius_m > 0 OR private_payload->>'visibility' = 'approximate'
        THEN 'radius'
    ELSE 'exact'
END;

UPDATE domain_accounts SET kind = 'garnrolle';
UPDATE domain_accounts
SET radius_m = CASE
    WHEN map_state = 'radius' AND radius_m = 0 THEN 250
    WHEN map_state <> 'radius' THEN 0
    ELSE radius_m
END;

ALTER TABLE domain_accounts
    ALTER COLUMN kind SET DEFAULT 'garnrolle',
    ALTER COLUMN mode DROP NOT NULL,
    ALTER COLUMN mode DROP DEFAULT,
    ALTER COLUMN map_state SET NOT NULL,
    ALTER COLUMN map_state SET DEFAULT 'not_on_map',
    ADD CONSTRAINT domain_accounts_kind_garnrolle
        CHECK (kind = 'garnrolle'),
    ADD CONSTRAINT domain_accounts_map_state_valid
        CHECK (map_state IN ('not_on_map', 'exact', 'radius')),
    ADD CONSTRAINT domain_accounts_map_state_location
        CHECK (
            map_state = 'not_on_map'
            OR (location_lat IS NOT NULL AND location_lon IS NOT NULL)
        ),
    ADD CONSTRAINT domain_accounts_radius_state_consistent
        CHECK (
            (map_state = 'radius' AND radius_m > 0)
            OR (map_state <> 'radius' AND radius_m = 0)
        );
