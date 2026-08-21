CREATE INDEX domain_outbox_published_readiness
    ON domain_outbox (published_at DESC, id DESC)
    WHERE published_at IS NOT NULL;

CREATE INDEX domain_outbox_quarantined_readiness
    ON domain_outbox (id)
    WHERE published_at IS NULL AND quarantined_at IS NOT NULL;
