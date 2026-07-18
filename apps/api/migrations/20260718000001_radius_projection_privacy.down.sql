-- Intentionally irreversible security rollback.
--
-- A rollback may occur after accounts have created safe random radius bindings.
-- Older application versions would ignore those bindings and recreate the known
-- reversible id-based projection. Therefore the down migration repeats the
-- fail-closed cutover for every currently mapped radius account instead of
-- restoring or retaining a public radius state. Private locations remain
-- available for a later safe reactivation.
UPDATE domain_accounts
SET map_state = 'not_on_map',
    radius_m = 0,
    private_payload = private_payload - 'radius_projection' - 'visibility',
    updated_at = NOW()
WHERE map_state = 'radius'
   OR radius_m > 0
   OR private_payload->>'visibility' = 'approximate';
