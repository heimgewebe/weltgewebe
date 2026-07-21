CREATE FUNCTION federation_canonical_neighbourhood_targets(targets JSONB)
RETURNS JSONB
LANGUAGE SQL
IMMUTABLE
STRICT
AS $$
    SELECT COALESCE(jsonb_agg(target ORDER BY target), '[]'::jsonb)
    FROM (
        SELECT DISTINCT jsonb_array_elements_text(targets) AS target
    ) canonical_targets
$$;

CREATE TABLE federation_event_receipts (
    event_id UUID PRIMARY KEY,
    envelope_sha256 TEXT NOT NULL CHECK (length(envelope_sha256) = 64),
    direction TEXT NOT NULL CHECK (direction IN ('inbox', 'outbox')),
    recorded_at TIMESTAMPTZ NOT NULL,
    UNIQUE (event_id, envelope_sha256)
);

-- Fail closed if legacy Inbox and Outbox ever reused one event_id: the primary
-- key makes the migration abort rather than silently choosing one direction.
INSERT INTO federation_event_receipts (event_id, envelope_sha256, direction, recorded_at)
SELECT event_id, envelope_sha256, 'inbox', received_at FROM federation_inbox
UNION ALL
SELECT event_id, envelope_sha256, 'outbox', created_at FROM federation_outbox;

ALTER TABLE federation_inbox
    ADD CONSTRAINT federation_inbox_event_receipt
        FOREIGN KEY (event_id, envelope_sha256)
        REFERENCES federation_event_receipts(event_id, envelope_sha256);

ALTER TABLE federation_outbox
    ADD CONSTRAINT federation_outbox_event_receipt
        FOREIGN KEY (event_id, envelope_sha256)
        REFERENCES federation_event_receipts(event_id, envelope_sha256);

CREATE FUNCTION federation_validate_event_receipt_direction()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    receipt_direction TEXT;
BEGIN
    SELECT direction INTO receipt_direction
    FROM federation_event_receipts
    WHERE event_id = NEW.event_id;

    IF receipt_direction IS NULL THEN
        RAISE EXCEPTION 'federation event receipt must be reserved before inbox/outbox insert';
    END IF;
    IF TG_TABLE_NAME = 'federation_inbox' AND receipt_direction <> 'inbox' THEN
        RAISE EXCEPTION 'federation event receipt direction does not permit inbox insert';
    END IF;
    IF TG_TABLE_NAME = 'federation_outbox' AND receipt_direction <> 'outbox' THEN
        RAISE EXCEPTION 'federation event receipt direction does not permit outbox insert';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER federation_inbox_event_receipt_direction
BEFORE INSERT OR UPDATE OF event_id, envelope_sha256 ON federation_inbox
FOR EACH ROW
EXECUTE FUNCTION federation_validate_event_receipt_direction();

CREATE TRIGGER federation_outbox_event_receipt_direction
BEFORE INSERT OR UPDATE OF event_id, envelope_sha256 ON federation_outbox
FOR EACH ROW
EXECUTE FUNCTION federation_validate_event_receipt_direction();

ALTER TABLE federation_objects
    ADD COLUMN neighbourhood_targets JSONB;

UPDATE federation_objects AS object
SET neighbourhood_targets = federation_canonical_neighbourhood_targets(
    COALESCE(
        (
            SELECT receipt.envelope -> 'neighbourhood_targets'
            FROM (
                SELECT inbox.envelope
                FROM federation_inbox AS inbox
                WHERE inbox.object_address = object.object_address
                  AND inbox.object_version = object.object_version
                UNION ALL
                SELECT outbox.envelope
                FROM federation_outbox AS outbox
                WHERE outbox.object_address = object.object_address
                  AND outbox.object_version = object.object_version
            ) AS receipt
            LIMIT 1
        ),
        '[]'::jsonb
    )
);

ALTER TABLE federation_objects
    ALTER COLUMN neighbourhood_targets SET DEFAULT '[]'::jsonb,
    ALTER COLUMN neighbourhood_targets SET NOT NULL,
    ADD CONSTRAINT federation_objects_neighbourhood_targets_array
        CHECK (jsonb_typeof(neighbourhood_targets) = 'array'),
    ADD CONSTRAINT federation_objects_canonical_neighbourhood_targets
        CHECK (
            neighbourhood_targets =
                federation_canonical_neighbourhood_targets(neighbourhood_targets)
        ),
    ADD CONSTRAINT federation_objects_scope_audience
        CHECK (
            (scope = 'global' AND neighbourhood_targets = '[]'::jsonb)
            OR
            (scope = 'neighbourhood' AND jsonb_array_length(neighbourhood_targets) > 0)
        );

CREATE FUNCTION federation_reject_immutable_object_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.origin_cell_id IS DISTINCT FROM OLD.origin_cell_id
        OR NEW.object_kind IS DISTINCT FROM OLD.object_kind
        OR NEW.scope IS DISTINCT FROM OLD.scope
        OR NEW.neighbourhood_targets IS DISTINCT FROM OLD.neighbourhood_targets
    THEN
        RAISE EXCEPTION 'federation object identity, scope, and audience are immutable';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER federation_objects_immutable_identity
BEFORE UPDATE ON federation_objects
FOR EACH ROW
EXECUTE FUNCTION federation_reject_immutable_object_identity();

CREATE FUNCTION federation_reject_peer_public_key_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.public_key IS DISTINCT FROM OLD.public_key THEN
        RAISE EXCEPTION 'federation peer public key is immutable for a cell/key id pair';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER federation_peer_keys_immutable_public_key
BEFORE UPDATE ON federation_peer_keys
FOR EACH ROW
EXECUTE FUNCTION federation_reject_peer_public_key_change();
