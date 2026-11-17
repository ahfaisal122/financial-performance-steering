-- FR-1.14: the gross loss ratio next to its 3-year rolling average (t-2 to t,
-- earned-weighted), per insurer and line group, Total row included.
-- The average and the gap are NULL until three years are loaded.
CREATE OR REPLACE VIEW analysis_rolling_avg AS
SELECT
    rolling.insurer,
    rolling.year,
    rolling.line_group,
    rolling.is_total,
    lr.gross_loss_ratio,
    rolling.loss_ratio_3y_avg,
    (lr.gross_loss_ratio - rolling.loss_ratio_3y_avg) * 100 AS gap_to_3y_avg_pts,
    rolling.years_in_window
FROM kpi_loss_ratio_3y_avg AS rolling
INNER JOIN kpi_gross_loss_ratio AS lr
    ON rolling.insurer = lr.insurer
    AND rolling.year = lr.year
    AND rolling.line_group = lr.line_group;
