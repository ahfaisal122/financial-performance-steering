-- FR-1.12: year over year per insurer and line group, Total row included.
-- GWP growth is a fraction, the loss ratio change is in percentage points.
-- An insurer's first loaded year has no prior year and is left out.
CREATE OR REPLACE VIEW analysis_yoy AS
SELECT
    growth.insurer,
    growth.year,
    growth.line_group,
    growth.is_total,
    growth.gwp_teur,
    growth.gwp_prior_teur,
    growth.gwp_growth,
    change.gross_loss_ratio,
    change.gross_loss_ratio_prior,
    change.loss_ratio_change_pts
FROM kpi_gwp_growth AS growth
INNER JOIN kpi_loss_ratio_change AS change
    ON growth.insurer = change.insurer
    AND growth.year = change.year
    AND growth.line_group = change.line_group
WHERE growth.year > (
    SELECT MIN(first.year)
    FROM mart_line_group_year AS first
    WHERE first.insurer = growth.insurer
);
