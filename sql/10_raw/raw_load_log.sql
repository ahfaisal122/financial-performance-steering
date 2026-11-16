-- FR-1.3: one row per loaded source file. A file whose content hash is already
-- here is not loaded again, so a second run leaves raw_s050102 untouched.
CREATE TABLE IF NOT EXISTS raw_load_log (
    source_file VARCHAR PRIMARY KEY,
    sha256 VARCHAR,
    row_count BIGINT,
    loaded_at TIMESTAMP
);
