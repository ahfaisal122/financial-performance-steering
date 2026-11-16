-- KPI: ceded share = R0140 / GWP, as a fraction. Shows reliance on reinsurance.
-- NULL when GWP is zero, negative or missing.
CREATE OR REPLACE VIEW kpi_ceded_share AS
SELECT
    insurer,
    year,
    line_group,
    is_total,
    ceded_written_teur,
    gwp_teur,
    CASE WHEN gwp_teur > 0 THEN ceded_written_teur::DOUBLE / gwp_teur::DOUBLE END
        AS ceded_share
FROM mart_line_group_year;
