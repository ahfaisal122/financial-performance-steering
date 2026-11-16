-- FR-1.5: GWP totals against the figures printed elsewhere in the reports.
-- GWP = R0110 + R0120 + R0130 in the total column (C0200).
-- status: ok or fail. A reference row with no matching data, or with a metric
-- other than gwp, fails.
CREATE OR REPLACE TABLE dq_reference_check AS
WITH gwp AS (
    SELECT
        insurer,
        year,
        SUM(value_teur) AS pipeline_value_teur
    FROM raw_s050102
    WHERE lob_code = 'C0200' AND row_code IN ('R0110', 'R0120', 'R0130')
    GROUP BY insurer, year
)

SELECT
    ref.insurer,
    ref.year,
    ref.metric,
    ref.value_teur AS reference_value_teur,
    gwp.pipeline_value_teur,
    gwp.pipeline_value_teur - ref.value_teur AS gap_teur,
    CASE
        WHEN ABS(gwp.pipeline_value_teur - ref.value_teur)
            <= getvariable('dq_reference_tolerance_teur') THEN 'ok'
        ELSE 'fail'
    END AS status,
    ref.source
FROM ref_dq_reference_values AS ref
LEFT JOIN gwp
    ON ref.insurer = gwp.insurer AND ref.year = gwp.year AND ref.metric = 'gwp'
ORDER BY ref.insurer, ref.year, ref.metric;
