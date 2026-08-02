DROP TRIGGER IF EXISTS webgemeindezentrum_location_history_append_only
    ON webgemeindezentrum_location_history;
DROP FUNCTION IF EXISTS reject_webgemeindezentrum_location_history_mutation();

DROP TRIGGER IF EXISTS webgemeindezentrum_location_change_history
    ON webgemeindezentren;
DROP FUNCTION IF EXISTS record_webgemeindezentrum_location_change();

ALTER TABLE ortswebereien
    DROP CONSTRAINT IF EXISTS ortswebereien_active_webgemeindezentrum_same_ortsweberei;

DROP TABLE IF EXISTS webgemeindezentrum_location_history;
DROP TABLE IF EXISTS webgemeindezentren;
DROP TABLE IF EXISTS ortswebereien;
DROP TABLE IF EXISTS gewebezellen;
