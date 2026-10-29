-- SMART 112: executed automatically by the postgres entrypoint the first time the
-- pgdata volume is initialised. Idempotent so it can be re-run safely.
CREATE EXTENSION IF NOT EXISTS postgis;

-- Surface the extension in psql logs for quick operator verification.
DO $$
BEGIN
    RAISE NOTICE 'SMART 112: PostGIS % enabled on database %', postgis_version(), current_database();
END
$$;
