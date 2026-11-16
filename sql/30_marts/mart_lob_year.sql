-- FR-1.10: one row per insurer, year and line (column code), without the total column.
-- Amounts in EUR thousand. A figure is NULL when none of its rows is reported;
-- a missing component (for example no R0130) is left out of the sum, not set to zero.
CREATE OR REPLACE TABLE mart_lob_year AS
SELECT
    fct.insurer,
    fct.year,
    fct.lob_code,
    lob.lob_name_en,
    lob.line_group,
    lob.business_type,
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
WHERE NOT lob.is_total
GROUP BY fct.insurer, fct.year, fct.lob_code, lob.lob_name_en, lob.line_group, lob.business_type
ORDER BY fct.insurer, fct.year, fct.lob_code;
