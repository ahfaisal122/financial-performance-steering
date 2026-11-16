-- FR-1.1: the SFCR S.05.01.02 files exactly as delivered, one row per file row.
-- value_teur is EUR thousand as reported; a dash in the report is NULL, never zero.
-- source_file is the path from the repo root; loaded_at is UTC.
-- Rows are inserted per file by cockpit.ingest.
CREATE TABLE IF NOT EXISTS raw_s050102 (
    insurer VARCHAR,
    year INTEGER,
    template VARCHAR,
    lob_code VARCHAR,
    lob_name_de VARCHAR,
    lob_name_en VARCHAR,
    business_type VARCHAR,
    row_code VARCHAR,
    metric VARCHAR,
    value_teur DECIMAL(18, 3),
    source_file VARCHAR,
    loaded_at TIMESTAMP
);
