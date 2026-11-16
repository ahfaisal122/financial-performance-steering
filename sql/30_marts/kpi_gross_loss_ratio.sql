-- KPI: gross loss ratio = gross claims / GEP, as a fraction. The main cross-company KPI.
-- NULL when GEP is zero, negative or missing: no ratio is shown on such a base.
CREATE OR REPLACE VIEW kpi_gross_loss_ratio AS
SELECT
    insurer,
    year,
    line_group,
    is_total,
    gross_claims_teur,
    gep_teur,
    CASE WHEN gep_teur > 0 THEN gross_claims_teur::DOUBLE / gep_teur::DOUBLE END
        AS gross_loss_ratio
FROM mart_line_group_year;
