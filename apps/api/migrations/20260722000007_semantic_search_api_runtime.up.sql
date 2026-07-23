-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T006
-- Required by the verified T003 PostgreSQL trigram and full-text ranking contract.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- T003 treats lexical representations as regenerable projection state. Persist
-- them here as well so T006 does not rebuild two weighted tsvectors for every
-- authorized node on every HTTP search request.
ALTER TABLE search_node_projections
    ADD COLUMN search_vector TSVECTOR,
    ADD COLUMN search_vector_simple TSVECTOR;

UPDATE search_node_projections
   SET search_vector =
       setweight(to_tsvector('german'::regconfig, coalesce(title, '')), 'A') ||
       setweight(to_tsvector('german'::regconfig, coalesce(array_to_string(tags, ' '), '')), 'B') ||
       setweight(to_tsvector('german'::regconfig, coalesce(searchable_text, '')), 'C') ||
       setweight(to_tsvector('simple'::regconfig, coalesce(kind, '') || ' ' || coalesce(language, '')), 'D'),
       search_vector_simple =
       setweight(to_tsvector('simple'::regconfig, coalesce(title, '')), 'A') ||
       setweight(to_tsvector('simple'::regconfig, coalesce(array_to_string(tags, ' '), '')), 'B') ||
       setweight(to_tsvector('simple'::regconfig, coalesce(searchable_text, '')), 'C') ||
       setweight(to_tsvector('simple'::regconfig, coalesce(kind, '') || ' ' || coalesce(language, '')), 'D');

ALTER TABLE search_node_projections
    ALTER COLUMN search_vector SET NOT NULL,
    ALTER COLUMN search_vector_simple SET NOT NULL;

CREATE OR REPLACE FUNCTION weltgewebe_search_refresh_lexical_vectors()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('german'::regconfig, coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('german'::regconfig, coalesce(array_to_string(NEW.tags, ' '), '')), 'B') ||
        setweight(to_tsvector('german'::regconfig, coalesce(NEW.searchable_text, '')), 'C') ||
        setweight(to_tsvector('simple'::regconfig, coalesce(NEW.kind, '') || ' ' || coalesce(NEW.language, '')), 'D');
    NEW.search_vector_simple :=
        setweight(to_tsvector('simple'::regconfig, coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple'::regconfig, coalesce(array_to_string(NEW.tags, ' '), '')), 'B') ||
        setweight(to_tsvector('simple'::regconfig, coalesce(NEW.searchable_text, '')), 'C') ||
        setweight(to_tsvector('simple'::regconfig, coalesce(NEW.kind, '') || ' ' || coalesce(NEW.language, '')), 'D');
    RETURN NEW;
END;
$$;

CREATE TRIGGER search_node_projections_refresh_lexical_vectors
BEFORE INSERT OR UPDATE OF title, tags, searchable_text, language, kind
ON search_node_projections
FOR EACH ROW EXECUTE FUNCTION weltgewebe_search_refresh_lexical_vectors();

CREATE INDEX search_node_projections_t006_fts
    ON search_node_projections USING GIN (search_vector);
CREATE INDEX search_node_projections_t006_fts_simple
    ON search_node_projections USING GIN (search_vector_simple);
CREATE INDEX search_node_projections_t006_searchable_text_trigram
    ON search_node_projections USING GIN (searchable_text gin_trgm_ops);
CREATE INDEX search_node_projections_t006_title_trigram
    ON search_node_projections USING GIN (title gin_trgm_ops);
CREATE INDEX search_node_projections_t006_tags
    ON search_node_projections USING GIN (tags);
CREATE INDEX search_node_projections_t006_eligible
    ON search_node_projections (generation_id, semantic_state, kind, language, node_id);
