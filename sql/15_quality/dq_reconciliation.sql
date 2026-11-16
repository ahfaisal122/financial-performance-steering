-- FR-1.4: the lines must add up to the total column (C0200) per insurer, year and row.
-- status: ok, fail (gap above the tolerance) or total_only.
-- R1200 and R1300 are reported in the total column only, so they have nothing to add up.
CREATE OR REPLACE TABLE dq_reconciliation AS
WITH by_row AS (
    SELECT
        insurer,
        year,
        row_code,
        COUNT(*) FILTER (WHERE lob_code <> 'C0200') AS line_count,
        SUM(value_teur) FILTER (WHERE lob_code <> 'C0200') AS sum_lines_teur,
        SUM(value_teur) FILTER (WHERE lob_code = 'C0200') AS total_teur
    FROM raw_s050102
    GROUP BY insurer, year, row_code
),

flagged AS (
    SELECT
        *,
        row_code IN ('R1200', 'R1300') AND line_count = 0 AS is_total_only
    FROM by_row
)

SELECT
    insurer,
    year,
    row_code,
    line_count,
    sum_lines_teur,
    total_teur,
    CASE
        WHEN NOT is_total_only THEN COALESCE(sum_lines_teur, 0) - COALESCE(total_teur, 0)
    END AS gap_teur,
    CASE
        WHEN is_total_only THEN 'total_only'
        WHEN ABS(COALESCE(sum_lines_teur, 0) - COALESCE(total_teur, 0))
            <= getvariable('dq_tolerance_teur') THEN 'ok'
        ELSE 'fail'
    END AS status
FROM flagged
ORDER BY insurer, year, row_code;
