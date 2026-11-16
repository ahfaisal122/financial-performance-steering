-- FR-1.8: one row per S.05.01.02 row code in the raw data.
-- block is the section of the template the row sits in.
-- measure is the mart column the row feeds. This is the one place that says which
-- row codes make up GWP, GEP and gross claims (requirements section 4).
-- Rows R0410 to R0500 and R1300 have no measure: loaded, kept out of V1 KPIs.
CREATE OR REPLACE TABLE dim_metric AS
SELECT
    row_code,
    MIN(metric) AS metric_name,
    CASE
        WHEN row_code BETWEEN 'R0110' AND 'R0200' THEN 'Premiums written'
        WHEN row_code BETWEEN 'R0210' AND 'R0300' THEN 'Premiums earned'
        WHEN row_code BETWEEN 'R0310' AND 'R0400' THEN 'Claims incurred'
        WHEN row_code BETWEEN 'R0410' AND 'R0500' THEN 'Changes in other technical provisions'
        WHEN row_code = 'R0550' THEN 'Expenses incurred'
        WHEN row_code IN ('R1200', 'R1300') THEN 'Other and total expenses'
        ELSE 'Unknown'
    END AS block,
    CASE
        WHEN row_code IN ('R0110', 'R0120', 'R0130') THEN 'gwp'
        WHEN row_code = 'R0140' THEN 'ceded_written'
        WHEN row_code = 'R0200' THEN 'net_written'
        WHEN row_code IN ('R0210', 'R0220', 'R0230') THEN 'gep'
        WHEN row_code = 'R0240' THEN 'ceded_earned'
        WHEN row_code = 'R0300' THEN 'net_earned'
        WHEN row_code IN ('R0310', 'R0320', 'R0330') THEN 'gross_claims'
        WHEN row_code = 'R0340' THEN 'ceded_claims'
        WHEN row_code = 'R0400' THEN 'net_claims'
        WHEN row_code = 'R0550' THEN 'expenses'
    END AS measure
FROM raw_s050102
GROUP BY row_code
ORDER BY row_code;
