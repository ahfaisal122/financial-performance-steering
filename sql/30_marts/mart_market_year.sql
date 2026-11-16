-- The German non-life market total per year, in EUR million (FR-1.2, FR-1.15).
-- Same row codes as the company figures: GWP = R0110 + R0120 + R0130, and so on.
-- They are written out here because dim_metric only knows the row codes the company
-- files happen to contain.
-- A figure is NULL when EIOPA delivers none of its rows (claims in 2016).
CREATE OR REPLACE TABLE mart_market_year AS
SELECT
    'German market' AS market,
    year,
    SUM(value_meur) FILTER (WHERE item_code IN ('R0110', 'R0120', 'R0130')) AS gwp_meur,
    SUM(value_meur) FILTER (WHERE item_code IN ('R0210', 'R0220', 'R0230')) AS gep_meur,
    SUM(value_meur) FILTER (WHERE item_code IN ('R0310', 'R0320', 'R0330'))
        AS gross_claims_meur
FROM stg_eiopa_nonlife
GROUP BY year
ORDER BY year;
