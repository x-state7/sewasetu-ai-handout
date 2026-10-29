-- SYNTHETIC DEMONSTRATION DATA ONLY. Not a real citizen export.
-- Change the dates to the current year if testing long after October 2026.
INSERT INTO applications (
    id, application_no, applicant_name, mobile, dob, gender, marital_status,
    village, block, bank_account, ifsc, status, submitted_at, decided_at, decided_by
) VALUES
(1, 'DEMO000001', 'Demo Citizen 01', '0000000001', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Sonari', '000000000', 'TEST0000000', 'PENDING', '2026-10-16 08:00:00', NULL, NULL),
(2, 'DEMO000002', 'Demo Citizen 02', '0000000002', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Rajapara', '000000000', 'TEST0000000', 'PENDING', '2026-10-16 08:00:00', NULL, NULL),
(3, 'DEMO000003', 'Demo Citizen 03', '0000000003', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Dhemaji Pathar', '000000000', 'TEST0000000', 'PENDING', '2026-10-16 08:00:00', NULL, NULL),
(4, 'DEMO000004', 'Demo Citizen 04', '0000000004', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Borgaon', '000000000', 'TEST0000000', 'APPROVED', '2026-10-16 08:00:00', '2026-10-16 09:00:00', 'demo-officer'),
(5, 'DEMO000005', 'Demo Citizen 05', '0000000005', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Namti', '000000000', 'TEST0000000', 'APPROVED', '2026-10-16 08:00:00', '2026-10-16 09:00:00', 'demo-officer'),
(6, 'DEMO000006', 'Demo Citizen 06', '0000000006', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Khelua', '000000000', 'TEST0000000', 'REJECTED', '2026-10-16 08:00:00', '2026-10-16 09:00:00', 'demo-officer'),
(7, 'DEMO000007', 'Demo Citizen 07', '0000000007', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Sonari', '000000000', 'TEST0000000', 'WITHDRAWN', '2026-10-16 08:00:00', '2026-10-16 09:00:00', 'DEMO-APPLICANT'),
(8, 'DEMO000008', 'Demo Citizen 08', '0000000008', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Rajapara', '000000000', 'TEST0000000', 'PENDING', '2026-10-16 08:00:00', NULL, NULL),
(9, 'DEMO000009', 'Demo Citizen 09', '0000000009', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Dhemaji Pathar', '000000000', 'TEST0000000', 'APPROVED', '2026-10-16 08:00:00', '2026-10-16 09:00:00', 'demo-officer'),
(10, 'DEMO000010', 'Demo Citizen 10', '0000000010', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Borgaon', '000000000', 'TEST0000000', 'PENDING', '2026-10-16 08:00:00', NULL, NULL),
(11, 'DEMO000011', 'Demo Citizen 11', '0000000011', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Namti', '000000000', 'TEST0000000', 'REJECTED', '2026-10-16 08:00:00', '2026-10-16 09:00:00', 'demo-officer'),
(12, 'DEMO000012', 'Demo Citizen 12', '0000000012', '1955-01-01', 'Other', 'Unmarried', 'Demo Village', 'Khelua', '000000000', 'TEST0000000', 'APPROVED', '2026-10-16 08:00:00', '2026-10-16 09:00:00', 'demo-officer');
SELECT setval('applications_id_seq', COALESCE((SELECT MAX(id) FROM applications), 1), true);
INSERT INTO audit_log(application_id, action, actor, note, at)
SELECT id, 'SUBMIT', 'demo-fixture', 'Synthetic fixture', submitted_at
FROM applications WHERE application_no LIKE 'DEMO%';
SELECT setval('audit_log_id_seq', COALESCE((SELECT MAX(id) FROM audit_log), 1), true);
