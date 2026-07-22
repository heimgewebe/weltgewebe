CREATE FUNCTION federation_reject_event_receipt_direction_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'federation event receipt direction is immutable';
END
$$;

CREATE TRIGGER federation_event_receipts_immutable_direction
BEFORE UPDATE OF direction ON federation_event_receipts
FOR EACH ROW
WHEN (NEW.direction IS DISTINCT FROM OLD.direction)
EXECUTE FUNCTION federation_reject_event_receipt_direction_change();

-- Validate legacy history against the already-frozen object scope and audience.
-- The two EXISTS scans fail fast on the first violation and avoid the global
-- GROUP BY / COUNT(DISTINCT jsonb) aggregation that would scale poorly.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM federation_inbox AS receipt
        JOIN federation_objects AS object USING (object_address)
        WHERE (receipt.envelope ->> 'scope') IS DISTINCT FROM object.scope
           OR federation_canonical_neighbourhood_targets(
                COALESCE(receipt.envelope -> 'neighbourhood_targets', '[]'::jsonb)
              ) IS DISTINCT FROM object.neighbourhood_targets
    ) OR EXISTS (
        SELECT 1
        FROM federation_outbox AS receipt
        JOIN federation_objects AS object USING (object_address)
        WHERE (receipt.envelope ->> 'scope') IS DISTINCT FROM object.scope
           OR federation_canonical_neighbourhood_targets(
                COALESCE(receipt.envelope -> 'neighbourhood_targets', '[]'::jsonb)
              ) IS DISTINCT FROM object.neighbourhood_targets
    ) THEN
        RAISE EXCEPTION 'legacy federation object history changed immutable scope or neighbourhood audience';
    END IF;
END
$$;
