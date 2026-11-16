-- KPI: gross written premium = R0110 + R0120 + R0130, in EUR thousand.
CREATE OR REPLACE VIEW kpi_gwp AS
SELECT
    insurer,
    year,
    line_group,
    is_total,
    gwp_teur
FROM mart_line_group_year;
