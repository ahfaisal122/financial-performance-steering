-- KPI: loss ratio change = LR(t) - LR(t-1), in percentage points (5 means +5 points).
-- The prior year is exactly t-1. NULL when either year has no loss ratio.
CREATE OR REPLACE VIEW kpi_loss_ratio_change AS
SELECT
    cur.insurer,
    cur.year,
    cur.line_group,
    cur.is_total,
    cur.gross_loss_ratio,
    prior.gross_loss_ratio AS gross_loss_ratio_prior,
    (cur.gross_loss_ratio - prior.gross_loss_ratio) * 100 AS loss_ratio_change_pts
FROM kpi_gross_loss_ratio AS cur
LEFT JOIN kpi_gross_loss_ratio AS prior
    ON cur.insurer = prior.insurer
    AND cur.line_group = prior.line_group
    AND cur.year - 1 = prior.year;
