DROP INDEX IF EXISTS federation_outbox_delivery_order;

DROP TABLE IF EXISTS federation_delivery_attempts;

ALTER TABLE federation_peer_relationships
    DROP COLUMN IF EXISTS delivery_policy_sha256,
    DROP COLUMN IF EXISTS delivery_base_url;
