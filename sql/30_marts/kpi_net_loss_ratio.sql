-- KPI: net loss ratio = R0400 / R0300, as a fraction.
-- Use within one company only: distorted by internal reinsurance.
-- NULL when net earned premium is zero, negative or missing.
CREATE OR REPLACE VIEW kpi_net_loss_ratio AS
SELECT
    insurer,
    year,
    line_group,
    is_total,
    net_claims_teur,
    net_earned_teur,
    CASE WHEN net_earned_teur > 0 THEN net_claims_teur::DOUBLE / net_earned_teur::DOUBLE END
        AS net_loss_ratio
FROM mart_line_group_year;
