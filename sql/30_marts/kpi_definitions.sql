-- FR-1.11: the KPI glossary from requirements section 4.
-- The dashboard tooltips and the V2 AI layer read from this table.
-- unit: TEUR, ratio (a fraction, 0.65 means 65%) or points (percentage points).
-- view_name and value_column say where the KPI is computed.
CREATE OR REPLACE TABLE kpi_definitions AS
SELECT *
FROM (
    VALUES
    (1, 'gwp', 'Gross written premium (GWP)', 'R0110 + R0120 + R0130',
        'All', NULL, 'TEUR', 'kpi_gwp', 'gwp_teur'),
    (2, 'gep', 'Gross earned premium (GEP)', 'R0210 + R0220 + R0230',
        'All', NULL, 'TEUR', 'kpi_gep', 'gep_teur'),
    (3, 'gross_claims', 'Gross claims incurred', 'R0310 + R0320 + R0330',
        'All', 'Mixes current-year claims and reserve changes on prior years',
        'TEUR', 'kpi_gross_claims', 'gross_claims_teur'),
    (4, 'gross_loss_ratio', 'Gross loss ratio', 'Gross claims / GEP',
        'All, cross-company', 'Main comparison KPI',
        'ratio', 'kpi_gross_loss_ratio', 'gross_loss_ratio'),
    (5, 'ceded_share', 'Ceded share', 'R0140 / GWP',
        'All', 'Shows reliance on reinsurance',
        'ratio', 'kpi_ceded_share', 'ceded_share'),
    (6, 'net_loss_ratio', 'Net loss ratio', 'R0400 / R0300',
        'Within one company', 'Distorted by internal reinsurance',
        'ratio', 'kpi_net_loss_ratio', 'net_loss_ratio'),
    (7, 'net_expense_ratio', 'Net expense ratio', 'R0550 / R0300',
        'Within one company', 'Flag on every view, never compare across companies',
        'ratio', 'kpi_net_expense_ratio', 'net_expense_ratio'),
    (8, 'gwp_growth', 'GWP growth', 'GWP(t) / GWP(t-1) - 1',
        'All', 'HGB basis, currency effects included',
        'ratio', 'kpi_gwp_growth', 'gwp_growth'),
    (9, 'loss_ratio_change', 'Loss ratio change', 'LR(t) - LR(t-1), in points',
        'All', NULL, 'points', 'kpi_loss_ratio_change', 'loss_ratio_change_pts'),
    (10, 'loss_ratio_3y_avg', '3-year average loss ratio',
        'Sum of claims / sum of GEP over t-2 to t',
        'All', 'Earned-weighted, not a mean of ratios',
        'ratio', 'kpi_loss_ratio_3y_avg', 'loss_ratio_3y_avg'),
    (11, 'mix_share', 'Mix share', 'GEP of a line / total GEP',
        'All', 'Drives the mix effect', 'ratio', 'kpi_mix_share', 'mix_share'),
    (12, 'peer_gap', 'Peer gap', 'LR(AGCS) - LR(HDI), in points',
        'Per line', NULL, 'points', 'kpi_peer_gap', 'peer_gap_pts'),
    (13, 'market_gap', 'Market gap', 'LR(company) - LR(German market), in points',
        'Total level only, from EIOPA',
        'Company books are global, the benchmark is Germany only',
        'points', 'kpi_market_gap', 'market_gap_pts')
) AS definitions (
    sort_order, kpi_id, kpi_name, formula, scope, caveat, unit, view_name, value_column
)
ORDER BY sort_order;
