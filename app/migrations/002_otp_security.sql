-- Step 3: shared OTP send and verification budgets across app/OAuth workers.
CREATE TABLE IF NOT EXISTS otp_send_attempts (
    id BIGSERIAL PRIMARY KEY,
    mobile VARCHAR(15) NOT NULL,
    attempted_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_otp_send_attempts_mobile_time
    ON otp_send_attempts(mobile, attempted_at);
CREATE TABLE IF NOT EXISTS otp_verify_attempts (
    id BIGSERIAL PRIMARY KEY,
    mobile VARCHAR(15) NOT NULL,
    attempted_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_otp_verify_attempts_mobile_time
    ON otp_verify_attempts(mobile, attempted_at);
CREATE INDEX IF NOT EXISTS idx_otps_mobile_created_at
    ON otps(mobile, created_at);
