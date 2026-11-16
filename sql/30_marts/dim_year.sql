-- FR-1.8: one row per reporting year in the raw data.
CREATE OR REPLACE TABLE dim_year AS
SELECT DISTINCT
    year,
    'FY ' || year AS year_label
FROM raw_s050102
ORDER BY year;
