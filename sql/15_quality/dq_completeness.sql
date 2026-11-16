-- FR-1.7: one row per missing combination. An empty table means complete.
-- missing_year: an insurer has no rows for a year between the first and last year loaded
--   (status fail, stops the run).
-- missing_main_line: an insurer has a year but no value for a main line group
--   (status warn, listed only).
CREATE OR REPLACE TABLE dq_completeness AS
WITH insurers AS (
    SELECT DISTINCT insurer FROM raw_s050102
),

expected_years AS (
    SELECT UNNEST(generate_series(MIN(year), MAX(year))) AS year
    FROM raw_s050102
),

present_years AS (
    SELECT DISTINCT insurer, year FROM raw_s050102
),

missing_years AS (
    SELECT insurers.insurer, expected_years.year
    FROM insurers
    CROSS JOIN expected_years
    ANTI JOIN present_years
        ON insurers.insurer = present_years.insurer
        AND expected_years.year = present_years.year
),

main_groups AS (
    SELECT DISTINCT line_group FROM ref_lob_groups WHERE is_main_line
),

present_groups AS (
    SELECT DISTINCT raw.insurer, raw.year, ref.line_group
    FROM raw_s050102 AS raw
    INNER JOIN ref_lob_groups AS ref ON raw.lob_code = ref.lob_code
    WHERE raw.value_teur IS NOT NULL
),

missing_lines AS (
    SELECT present_years.insurer, present_years.year, main_groups.line_group
    FROM present_years
    CROSS JOIN main_groups
    ANTI JOIN present_groups
        ON present_years.insurer = present_groups.insurer
        AND present_years.year = present_groups.year
        AND main_groups.line_group = present_groups.line_group
)

SELECT
    'missing_year' AS check_type,
    insurer,
    year,
    NULL::VARCHAR AS line_group,
    'fail' AS status
FROM missing_years
UNION ALL
SELECT
    'missing_main_line' AS check_type,
    insurer,
    year,
    line_group,
    'warn' AS status
FROM missing_lines
ORDER BY check_type, insurer, year, line_group;
