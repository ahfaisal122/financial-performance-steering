-- The German non-life market from EIOPA: one row per year and item code.
-- item_code uses the same row codes as S.05.01.02 (R0110 = gross written, direct business).
-- value_meur is EUR million, rounded to the 6 decimals the file delivers, so sums are exact.
CREATE OR REPLACE TABLE stg_eiopa_nonlife AS
SELECT
    reporting_country AS country,
    CAST(substr(reference_period, 2) AS INTEGER) AS year,
    item_code,
    item,
    CAST(value AS DECIMAL(24, 6)) AS value_meur,
    source_file
FROM raw_eiopa
WHERE business_type = 'Non-Life'
ORDER BY year, item_code;
