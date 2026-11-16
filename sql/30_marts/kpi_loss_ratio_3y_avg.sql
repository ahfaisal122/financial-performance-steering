-- KPI: 3-year average loss ratio = sum of gross claims / sum of GEP over t-2 to t.
-- Earned-weighted, not a mean of the three ratios.
-- NULL unless all three years have claims and GEP, and the summed GEP is above zero.
CREATE OR REPLACE VIEW kpi_loss_ratio_3y_avg AS
SELECT
    cur.insurer,
    cur.year,
    cur.line_group,
    cur.is_total,
    COUNT(win.year) AS years_in_window,
    SUM(win.gross_claims_teur) AS gross_claims_3y_teur,
    SUM(win.gep_teur) AS gep_3y_teur,
    CASE
        WHEN COUNT(win.gross_claims_teur) = 3 AND COUNT(win.gep_teur) = 3 AND SUM(win.gep_teur) > 0
            THEN SUM(win.gross_claims_teur)::DOUBLE / SUM(win.gep_teur)::DOUBLE
    END AS loss_ratio_3y_avg
FROM mart_line_group_year AS cur
INNER JOIN mart_line_group_year AS win
    ON cur.insurer = win.insurer
    AND cur.line_group = win.line_group
    AND win.year BETWEEN cur.year - 2 AND cur.year
GROUP BY cur.insurer, cur.year, cur.line_group, cur.is_total;
