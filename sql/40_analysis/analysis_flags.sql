-- FR-1.16: rule-based flags, one row per flag with the numbers behind it.
-- The V2 commentary reads from this view.
--   lr_move_above_3y_avg:    the loss ratio moved more than the threshold (up or down)
--                            and sits above its 3-year average.
--   peer_moved_other_way:    the focus company's loss ratio moved more than the threshold
--                            and the peer's moved in the opposite direction.
--   growth_slowed_two_years: GWP growth fell in each of the last two years.
-- The threshold is 5 percentage points, written out below: a view is computed when it
-- is read (for example by Power BI), so it cannot depend on a pipeline setting.
-- The move is rounded to 4 decimals before the comparison, so a move of exactly 5 points
-- is not flagged because of floating-point noise.
-- Columns a rule does not use are NULL.
CREATE OR REPLACE VIEW analysis_flags AS
WITH changes AS (
    SELECT
        change.insurer,
        change.year,
        change.line_group,
        change.is_total,
        change.gross_loss_ratio,
        change.loss_ratio_change_pts,
        insurer.role
    FROM kpi_loss_ratio_change AS change
    INNER JOIN dim_insurer AS insurer ON change.insurer = insurer.insurer
)

SELECT
    'lr_move_above_3y_avg' AS flag,
    changes.insurer,
    changes.year,
    changes.line_group,
    changes.is_total,
    changes.gross_loss_ratio,
    changes.loss_ratio_change_pts,
    rolling.loss_ratio_3y_avg,
    NULL::VARCHAR AS peer_insurer,
    NULL::DOUBLE AS peer_loss_ratio_change_pts,
    NULL::DOUBLE AS gwp_growth,
    NULL::DOUBLE AS gwp_growth_prior,
    NULL::DOUBLE AS gwp_growth_two_years_ago
FROM changes
INNER JOIN kpi_loss_ratio_3y_avg AS rolling
    ON changes.insurer = rolling.insurer
    AND changes.year = rolling.year
    AND changes.line_group = rolling.line_group
WHERE ABS(ROUND(changes.loss_ratio_change_pts, 4)) > 5
    AND changes.gross_loss_ratio > rolling.loss_ratio_3y_avg
UNION ALL
SELECT
    'peer_moved_other_way' AS flag,
    focus.insurer,
    focus.year,
    focus.line_group,
    focus.is_total,
    focus.gross_loss_ratio,
    focus.loss_ratio_change_pts,
    NULL::DOUBLE AS loss_ratio_3y_avg,
    peer.insurer AS peer_insurer,
    peer.loss_ratio_change_pts AS peer_loss_ratio_change_pts,
    NULL::DOUBLE AS gwp_growth,
    NULL::DOUBLE AS gwp_growth_prior,
    NULL::DOUBLE AS gwp_growth_two_years_ago
FROM changes AS focus
INNER JOIN changes AS peer
    ON focus.year = peer.year
    AND focus.line_group = peer.line_group
    AND peer.role = 'peer'
WHERE focus.role = 'focus'
    AND ABS(ROUND(focus.loss_ratio_change_pts, 4)) > 5
    AND focus.loss_ratio_change_pts * peer.loss_ratio_change_pts < 0
UNION ALL
SELECT
    'growth_slowed_two_years' AS flag,
    cur.insurer,
    cur.year,
    cur.line_group,
    cur.is_total,
    NULL::DOUBLE AS gross_loss_ratio,
    NULL::DOUBLE AS loss_ratio_change_pts,
    NULL::DOUBLE AS loss_ratio_3y_avg,
    NULL::VARCHAR AS peer_insurer,
    NULL::DOUBLE AS peer_loss_ratio_change_pts,
    cur.gwp_growth,
    prior.gwp_growth AS gwp_growth_prior,
    two_ago.gwp_growth AS gwp_growth_two_years_ago
FROM kpi_gwp_growth AS cur
INNER JOIN kpi_gwp_growth AS prior
    ON cur.insurer = prior.insurer
    AND cur.line_group = prior.line_group
    AND cur.year - 1 = prior.year
INNER JOIN kpi_gwp_growth AS two_ago
    ON cur.insurer = two_ago.insurer
    AND cur.line_group = two_ago.line_group
    AND cur.year - 2 = two_ago.year
WHERE cur.gwp_growth < prior.gwp_growth
    AND prior.gwp_growth < two_ago.gwp_growth;
