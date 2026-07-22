DROP TRIGGER IF EXISTS federation_event_receipts_immutable_direction ON federation_event_receipts;
DROP FUNCTION IF EXISTS federation_reject_event_receipt_direction_change();

DROP TRIGGER IF EXISTS federation_outbox_event_receipt_direction ON federation_outbox;
DROP TRIGGER IF EXISTS federation_inbox_event_receipt_direction ON federation_inbox;
DROP FUNCTION IF EXISTS federation_validate_event_receipt_direction();

ALTER TABLE federation_outbox
    DROP CONSTRAINT IF EXISTS federation_outbox_event_receipt;
ALTER TABLE federation_inbox
    DROP CONSTRAINT IF EXISTS federation_inbox_event_receipt;
DROP TABLE IF EXISTS federation_event_receipts;

DROP TRIGGER IF EXISTS federation_peer_keys_immutable_public_key ON federation_peer_keys;
DROP FUNCTION IF EXISTS federation_reject_peer_public_key_change();

DROP TRIGGER IF EXISTS federation_objects_immutable_identity ON federation_objects;
DROP FUNCTION IF EXISTS federation_reject_immutable_object_identity();

ALTER TABLE federation_objects
    DROP CONSTRAINT IF EXISTS federation_objects_scope_audience,
    DROP CONSTRAINT IF EXISTS federation_objects_canonical_neighbourhood_targets,
    DROP CONSTRAINT IF EXISTS federation_objects_neighbourhood_targets_array,
    DROP COLUMN IF EXISTS neighbourhood_targets;

DROP FUNCTION IF EXISTS federation_canonical_neighbourhood_targets(JSONB);
