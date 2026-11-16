-- KPI: mix share = GEP of a line group / total GEP, as a fraction. Drives the mix effect.
-- Total GEP here is the sum of the line groups, not the reported C0200 figure, so the
-- shares of one insurer and year add up to exactly 1. The Total row is left out.
-- NULL when the summed GEP is zero, negative or missing.
CREATE OR REPLACE VIEW kpi_mix_share AS
WITH line_groups AS (
    SELECT
        insurer,
        year,
        line_group,
        gep_teur,
        SUM(gep_teur) OVER (PARTITION BY insurer, year) AS gep_all_lines_teur
    FROM mart_line_group_year
    WHERE NOT is_total
)

SELECT
    insurer,
    year,
    line_group,
    gep_teur,
    gep_all_lines_teur,
    CASE WHEN gep_all_lines_teur > 0 THEN gep_teur::DOUBLE / gep_all_lines_teur::DOUBLE END
        AS mix_share
FROM line_groups;
