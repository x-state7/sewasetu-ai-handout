-- Apply ONCE to a running database after backing it up.
-- Fresh databases receive these indexes through app/schema.sql.
-- This migration intentionally fails if existing duplicates need cleanup.
BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM applications
        WHERE status IN ('PENDING', 'APPROVED', 'DEEMED_APPROVED')
        GROUP BY mobile HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Duplicate active mobile applications; inspect before migration';
    END IF;
    IF EXISTS (
        SELECT 1 FROM applications WHERE application_no IS NOT NULL
        GROUP BY application_no HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Duplicate application numbers; inspect before migration';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_app_active_mobile
  ON applications (mobile)
  WHERE status IN ('PENDING', 'APPROVED', 'DEEMED_APPROVED');

CREATE UNIQUE INDEX IF NOT EXISTS uq_app_application_no
  ON applications (application_no)
  WHERE application_no IS NOT NULL;

COMMIT;
