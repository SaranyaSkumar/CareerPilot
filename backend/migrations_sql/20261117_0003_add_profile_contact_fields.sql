-- CareerPilot optional profile contact fields.
-- Apply once in the Supabase SQL editor (project kcrtedhezyovfygfotia).
-- This script only adds columns on career_profiles. It does not drop tables,
-- delete rows, or disable row level security.
-- The API process does not run it: careerpilot_app has no ALTER privilege.
-- Grants below are table-level, so they cover the new columns. They are
-- repeated so a restored careerpilot_app role still has DML. RLS stays enabled.
-- The backend must keep filtering by user_id: careerpilot_app has BYPASSRLS.

ALTER TABLE career_profiles
    ADD COLUMN IF NOT EXISTS phone character varying(40) NOT NULL DEFAULT '';

ALTER TABLE career_profiles
    ADD COLUMN IF NOT EXISTS website_url character varying(500) NOT NULL DEFAULT '';

ALTER TABLE career_profiles
    ADD COLUMN IF NOT EXISTS linkedin_url character varying(500) NOT NULL DEFAULT '';

ALTER TABLE career_profiles
    ADD COLUMN IF NOT EXISTS github_url character varying(500) NOT NULL DEFAULT '';

ALTER TABLE career_profiles ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON TABLE career_profiles FROM anon';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE career_profiles TO authenticated';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        EXECUTE 'GRANT ALL ON TABLE career_profiles TO service_role';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'careerpilot_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE career_profiles TO careerpilot_app';
    END IF;
END $$;
