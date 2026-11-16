-- KPI: peer gap = LR(focus company) - LR(peer), in percentage points, per line group and year.
-- Focus and peer come from dim_insurer.role (AGCS and HDI in reference/insurers.csv).
-- Every line group of the focus company is listed; the gap is NULL when the peer has
-- no loss ratio for that line group and year.
-- peer_status says why a gap is missing, so the dashboard can show the text instead
-- of a blank: 'ok', 'no peer data' or 'no focus data'.
CREATE OR REPLACE VIEW kpi_peer_gap AS
WITH loss_ratios AS (
    SELECT
        lr.insurer,
        lr.year,
        lr.line_group,
        lr.is_total,
        lr.gross_loss_ratio,
        insurer.role
    FROM kpi_gross_loss_ratio AS lr
    INNER JOIN dim_insurer AS insurer ON lr.insurer = insurer.insurer
)

SELECT
    focus.year,
    focus.line_group,
    focus.is_total,
    focus.insurer AS focus_insurer,
    peer.insurer AS peer_insurer,
    focus.gross_loss_ratio AS focus_loss_ratio,
    peer.gross_loss_ratio AS peer_loss_ratio,
    (focus.gross_loss_ratio - peer.gross_loss_ratio) * 100 AS peer_gap_pts,
    CASE
        WHEN peer.gross_loss_ratio IS NULL THEN 'no peer data'
        WHEN focus.gross_loss_ratio IS NULL THEN 'no focus data'
        ELSE 'ok'
    END AS peer_status
FROM loss_ratios AS focus
LEFT JOIN loss_ratios AS peer
    ON focus.year = peer.year
    AND focus.line_group = peer.line_group
    AND peer.role = 'peer'
WHERE focus.role = 'focus';
