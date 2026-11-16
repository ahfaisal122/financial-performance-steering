-- KPI: gross claims incurred = R0310 + R0320 + R0330, in EUR thousand.
-- Mixes current-year claims and reserve changes on prior years.
CREATE OR REPLACE VIEW kpi_gross_claims AS
SELECT
    insurer,
    year,
    line_group,
    is_total,
    gross_claims_teur
FROM mart_line_group_year;
