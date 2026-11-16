-- One row per insurer, year and line group, plus one row for the company total.
-- Every KPI view reads from this table.
-- The Total row (is_total) is the total column C0200 as reported, so it equals the
-- SFCR figure exactly. The line group rows add up to it within the 3 TEUR rounding
-- tolerance checked in dq_reconciliation.
CREATE OR REPLACE TABLE mart_line_group_year AS
SELECT
    fct.insurer,
    fct.year,
    lob.line_group,
    lob.is_total,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'gwp') AS gwp_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'gep') AS gep_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'gross_claims') AS gross_claims_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'ceded_written') AS ceded_written_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'ceded_earned') AS ceded_earned_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'ceded_claims') AS ceded_claims_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'net_written') AS net_written_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'net_earned') AS net_earned_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'net_claims') AS net_claims_teur,
    SUM(fct.value_teur) FILTER (WHERE metric.measure = 'expenses') AS expenses_teur
FROM fct_s050102 AS fct
INNER JOIN dim_lob AS lob ON fct.lob_code = lob.lob_code
INNER JOIN dim_metric AS metric ON fct.row_code = metric.row_code
GROUP BY fct.insurer, fct.year, lob.line_group, lob.is_total
ORDER BY fct.insurer, fct.year, lob.is_total, lob.line_group;
