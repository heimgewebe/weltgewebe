-- Security cutover for issue #1464. Historical radius positions were derived
-- from public account ids and were therefore reversible. There is no safe
-- deterministic backfill: every existing radius account is hidden until its
-- owner explicitly saves the profile and receives a private random binding.
-- The exact private location remains intact for that controlled reactivation.
DO $$
DECLARE
    affected_rows BIGINT;
BEGIN
    UPDATE domain_accounts
    SET map_state = 'not_on_map',
        radius_m = 0,
        private_payload = private_payload - 'radius_projection' - 'visibility',
        updated_at = NOW()
    WHERE map_state = 'radius'
       OR radius_m > 0
       OR private_payload->>'visibility' = 'approximate';

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RAISE NOTICE 'radius projection privacy cutover hid % account(s)', affected_rows;
END
$$;
