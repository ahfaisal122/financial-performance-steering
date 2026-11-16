-- KPI: net expense ratio = R0550 / R0300, as a fraction.
-- Never compare across companies: R0550 is net of reinsurance commissions and each
-- company books those differently (data rule 5).
-- NULL when net earned premium is zero, negative or missing.
CREATE OR REPLACE VIEW kpi_net_expense_ratio AS
SELECT
    insurer,
    year,
    line_group,
    is_total,
    expenses_teur,
    net_earned_teur,
    CASE WHEN net_earned_teur > 0 THEN expenses_teur::DOUBLE / net_earned_teur::DOUBLE END
        AS net_expense_ratio
FROM mart_line_group_year;
