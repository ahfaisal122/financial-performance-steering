-- KPI: gross earned premium = R0210 + R0220 + R0230, in EUR thousand.
CREATE OR REPLACE VIEW kpi_gep AS
SELECT
    insurer,
    year,
    line_group,
    is_total,
    gep_teur
FROM mart_line_group_year;
