-- KPI: GWP growth = GWP(t) / GWP(t-1) - 1, as a fraction. HGB basis, currency effects included.
-- The prior year is exactly t-1; a gap in the years is not bridged.
-- NULL when there is no prior year or the prior GWP is zero, negative or missing.
CREATE OR REPLACE VIEW kpi_gwp_growth AS
SELECT
    cur.insurer,
    cur.year,
    cur.line_group,
    cur.is_total,
    cur.gwp_teur,
    prior.gwp_teur AS gwp_prior_teur,
    CASE WHEN prior.gwp_teur > 0 THEN cur.gwp_teur::DOUBLE / prior.gwp_teur::DOUBLE - 1 END
        AS gwp_growth
FROM mart_line_group_year AS cur
LEFT JOIN mart_line_group_year AS prior
    ON cur.insurer = prior.insurer
    AND cur.line_group = prior.line_group
    AND cur.year - 1 = prior.year;
