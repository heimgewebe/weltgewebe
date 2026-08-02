-- Introduce the first executable Ortsweberei / Gewebezelle / Webgemeindezentrum
-- slice. These are stable collective structures, not user-created Knoten.
--
-- The circular, deferred foreign key is deliberate:
--   * every Ortsweberei must name exactly one active Webgemeindezentrum;
--   * the named centre must belong to that same Ortsweberei;
--   * a centre belongs to exactly one Ortsweberei.
-- PostgreSQL therefore enforces the one-to-one relation even for direct SQL
-- writes and future governance commands.

CREATE TABLE gewebezellen (
    id TEXT PRIMARY KEY
        CHECK (
            length(id) BETWEEN 3 AND 64
            AND id ~ '^[a-z0-9][a-z0-9.-]*[a-z0-9]$'
        ),
    lifecycle_state TEXT NOT NULL DEFAULT 'active'
        CHECK (lifecycle_state IN ('active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (updated_at >= created_at)
);

CREATE TABLE ortswebereien (
    id TEXT PRIMARY KEY
        CHECK (length(id) BETWEEN 3 AND 96),
    slug TEXT NOT NULL UNIQUE
        CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
    name TEXT NOT NULL
        CHECK (length(btrim(name)) BETWEEN 1 AND 160),
    description TEXT NOT NULL
        CHECK (length(btrim(description)) BETWEEN 1 AND 2000),
    gewebezelle_id TEXT NOT NULL UNIQUE
        REFERENCES gewebezellen(id) ON DELETE RESTRICT,
    lifecycle_state TEXT NOT NULL DEFAULT 'active'
        CHECK (lifecycle_state IN ('active', 'archived')),
    active_webgemeindezentrum_id TEXT NOT NULL
        UNIQUE DEFERRABLE INITIALLY DEFERRED,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (updated_at >= created_at)
);

CREATE TABLE webgemeindezentren (
    id TEXT PRIMARY KEY
        CHECK (length(id) BETWEEN 3 AND 128),
    ortsweberei_id TEXT NOT NULL UNIQUE
        REFERENCES ortswebereien(id) ON DELETE RESTRICT,
    name TEXT NOT NULL
        CHECK (length(btrim(name)) BETWEEN 1 AND 160),
    location_state TEXT NOT NULL
        CHECK (
            location_state IN (
                'desired',
                'provisional',
                'confirmed',
                'unavailable',
                'relocation_proposed'
            )
        ),
    lat DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon DOUBLE PRECISION NOT NULL CHECK (lon BETWEEN -180 AND 180),
    location_label TEXT NOT NULL
        CHECK (length(btrim(location_label)) BETWEEN 1 AND 500),
    meeting_note TEXT NOT NULL
        CHECK (length(btrim(meeting_note)) BETWEEN 1 AND 4000),
    access_note TEXT NOT NULL
        CHECK (length(btrim(access_note)) BETWEEN 1 AND 4000),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (updated_at >= created_at),
    UNIQUE (id, ortsweberei_id)
);

ALTER TABLE ortswebereien
    ADD CONSTRAINT ortswebereien_active_webgemeindezentrum_same_ortsweberei
    FOREIGN KEY (active_webgemeindezentrum_id, id)
    REFERENCES webgemeindezentren(id, ortsweberei_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE webgemeindezentrum_location_history (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    webgemeindezentrum_id TEXT NOT NULL
        REFERENCES webgemeindezentren(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL
        CHECK (
            event_type IN (
                'placement_desired',
                'placement_provisional',
                'placement_confirmed',
                'marked_unavailable',
                'relocation_proposed',
                'moved'
            )
        ),
    location_state TEXT NOT NULL
        CHECK (
            location_state IN (
                'desired',
                'provisional',
                'confirmed',
                'unavailable',
                'relocation_proposed'
            )
        ),
    lat DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon DOUBLE PRECISION NOT NULL CHECK (lon BETWEEN -180 AND 180),
    location_label TEXT NOT NULL
        CHECK (length(btrim(location_label)) BETWEEN 1 AND 500),
    reason TEXT NOT NULL
        CHECK (length(btrim(reason)) BETWEEN 1 AND 4000),
    decided_at TIMESTAMPTZ NOT NULL,
    UNIQUE (webgemeindezentrum_id, event_id)
);

CREATE INDEX webgemeindezentrum_location_history_timeline
    ON webgemeindezentrum_location_history (
        webgemeindezentrum_id,
        decided_at DESC,
        event_id DESC
    );

CREATE FUNCTION record_webgemeindezentrum_location_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    derived_event_type TEXT;
BEGIN
    IF ROW(OLD.location_state, OLD.lat, OLD.lon, OLD.location_label)
       IS NOT DISTINCT FROM
       ROW(NEW.location_state, NEW.lat, NEW.lon, NEW.location_label) THEN
        RETURN NEW;
    END IF;

    IF NEW.updated_at <= OLD.updated_at THEN
        RAISE EXCEPTION
            'Webgemeindezentrum location changes require a later updated_at';
    END IF;

    derived_event_type := CASE
        WHEN OLD.location_state = NEW.location_state THEN 'moved'
        WHEN NEW.location_state = 'desired' THEN 'placement_desired'
        WHEN NEW.location_state = 'provisional' THEN 'placement_provisional'
        WHEN NEW.location_state = 'confirmed' THEN 'placement_confirmed'
        WHEN NEW.location_state = 'unavailable' THEN 'marked_unavailable'
        WHEN NEW.location_state = 'relocation_proposed' THEN 'relocation_proposed'
        ELSE 'moved'
    END;

    INSERT INTO webgemeindezentrum_location_history (
        webgemeindezentrum_id,
        event_type,
        location_state,
        lat,
        lon,
        location_label,
        reason,
        decided_at
    ) VALUES (
        NEW.id,
        derived_event_type,
        NEW.location_state,
        NEW.lat,
        NEW.lon,
        NEW.location_label,
        'Standortänderung durch den kanonischen Datenbankvertrag.',
        NEW.updated_at
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER webgemeindezentrum_location_change_history
AFTER UPDATE OF location_state, lat, lon, location_label
ON webgemeindezentren
FOR EACH ROW
EXECUTE FUNCTION record_webgemeindezentrum_location_change();

CREATE FUNCTION reject_webgemeindezentrum_location_history_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Webgemeindezentrum location history is append-only';
END;
$$;

CREATE TRIGGER webgemeindezentrum_location_history_append_only
BEFORE UPDATE OR DELETE
ON webgemeindezentrum_location_history
FOR EACH ROW
EXECUTE FUNCTION reject_webgemeindezentrum_location_history_mutation();

-- The user chose this approximate point on a green area in Hammer Park on
-- 2026-08-02. `desired` is explicit: this is a collective intention, not a
-- claim of reservation, permission, permanent availability or accessibility.
INSERT INTO gewebezellen (
    id,
    lifecycle_state,
    created_at,
    updated_at
) VALUES (
    'hamm.weltgewebe.net',
    'active',
    '2026-08-02T10:08:00Z',
    '2026-08-02T10:08:00Z'
);

INSERT INTO ortswebereien (
    id,
    slug,
    name,
    description,
    gewebezelle_id,
    lifecycle_state,
    active_webgemeindezentrum_id,
    created_at,
    updated_at
) VALUES (
    'ortsweberei-hamm',
    'hamm',
    'Ortsweberei Hamm',
    'Die erste lokale Ortsweberei der bisherigen Gewebezelle.',
    'hamm.weltgewebe.net',
    'active',
    'webgemeindezentrum-hammer-park',
    '2026-08-02T10:08:00Z',
    '2026-08-02T10:08:00Z'
);

INSERT INTO webgemeindezentren (
    id,
    ortsweberei_id,
    name,
    location_state,
    lat,
    lon,
    location_label,
    meeting_note,
    access_note,
    created_at,
    updated_at
) VALUES (
    'webgemeindezentrum-hammer-park',
    'ortsweberei-hamm',
    'Webgemeindezentrum Hammer Park',
    'desired',
    53.5585,
    10.0580,
    'Hammer Park – gewünschter Treffpunkt auf der Grünfläche',
    'Ein bewusst gewählter öffentlicher Treffpunkt, an dem die Ortsweberei tatsächlich zusammenkommen kann. Die genaue Stelle kann später gemeinsam präzisiert werden.',
    'Gewünschter Treffort: Nutzung, Barrierefreiheit und regelmäßige Verfügbarkeit sind noch nicht bestätigt.',
    '2026-08-02T10:08:00Z',
    '2026-08-02T10:08:00Z'
);

INSERT INTO webgemeindezentrum_location_history (
    webgemeindezentrum_id,
    event_type,
    location_state,
    lat,
    lon,
    location_label,
    reason,
    decided_at
) VALUES (
    'webgemeindezentrum-hammer-park',
    'placement_desired',
    'desired',
    53.5585,
    10.0580,
    'Hammer Park – gewünschter Treffpunkt auf der Grünfläche',
    'Erste Ortsweberei: gewünschter gemeinsamer Treffpunkt auf einer Grünfläche im Hammer Park.',
    '2026-08-02T10:08:00Z'
);
