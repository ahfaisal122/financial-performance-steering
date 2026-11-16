-- FR-1.8: one row per insurer in the raw data.
-- An insurer missing from reference/insurers.csv keeps its full name and gets role 'other'.
CREATE OR REPLACE TABLE dim_insurer AS
SELECT
    raw.insurer,
    COALESCE(ref.insurer_short, raw.insurer) AS insurer_short,
    COALESCE(ref.role, 'other') AS role
FROM (SELECT DISTINCT insurer FROM raw_s050102) AS raw
LEFT JOIN ref_insurers AS ref ON raw.insurer = ref.insurer
ORDER BY raw.insurer;
