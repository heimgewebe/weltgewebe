-- pg_trgm is a shared database capability and may predate T006.
-- Deliberately retain it on rollback rather than dropping a shared extension.
SELECT 1;
