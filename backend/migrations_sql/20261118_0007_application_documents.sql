-- Attach a user's saved CV version and application-specific cover letter.
ALTER TABLE job_applications
    ADD COLUMN cv_version_id integer REFERENCES cv_versions(id) ON DELETE SET NULL,
    ADD COLUMN cover_letter text NOT NULL DEFAULT '';
CREATE INDEX job_applications_cv_version_idx ON job_applications (cv_version_id);
