-- KPI: market gap = LR(company) - LR(German market), in percentage points.
-- V1: company total against the German non-life market total from EIOPA. The by-line
-- gap waits for the GDV reference file (FR-1.23).
-- The company books are global; the benchmark is the German market only.
-- market_status says why a gap is missing: 'ok', 'no market data' or 'no company data'.
CREATE OR REPLACE VIEW kpi_market_gap AS
WITH market AS (
    SELECT
        market,
        year,
        CASE WHEN gep_meur > 0 THEN gross_claims_meur::DOUBLE / gep_meur::DOUBLE END
            AS market_loss_ratio
    FROM mart_market_year
)

SELECT
    company.insurer,
    company.year,
    company.line_group,
    company.is_total,
    company.gross_loss_ratio AS company_loss_ratio,
    market.market,
    market.market_loss_ratio,
    (company.gross_loss_ratio - market.market_loss_ratio) * 100 AS market_gap_pts,
    CASE
        WHEN market.market_loss_ratio IS NULL THEN 'no market data'
        WHEN company.gross_loss_ratio IS NULL THEN 'no company data'
        ELSE 'ok'
    END AS market_status
FROM kpi_gross_loss_ratio AS company
LEFT JOIN market ON company.year = market.year
WHERE company.is_total;
