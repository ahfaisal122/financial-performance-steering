-- FR-1.2: the EIOPA insurance statistics (Solo, Annual, premiums, claims and expenses),
-- rows of the reporting country Germany only, all years, values as delivered.
-- The file has no line of business: business_type is Life or Non-Life.
-- reference_period is text as delivered ('Y2025'); value is in EUR million.
-- Rows are inserted by cockpit.ingest.
CREATE TABLE IF NOT EXISTS raw_eiopa (
    reporting_country VARCHAR,
    reference_period VARCHAR,
    item VARCHAR,
    business_type VARCHAR,
    item_code VARCHAR,
    value DOUBLE,
    extraction_date VARCHAR,
    submissions INTEGER,
    source_file VARCHAR,
    loaded_at TIMESTAMP
);
