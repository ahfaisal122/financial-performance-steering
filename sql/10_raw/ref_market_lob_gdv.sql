-- FR-1.23: German market loss ratios by line group, typed in by hand from the GDV
-- statistics booklet, one row per year and line group with the table and page cited.
-- loss_ratio_pct is in percent (64.5 means 64.5%). ratio_type says which loss ratio the
-- source prints: 'current_year' (claims of the business year only) or 'balance_sheet'
-- (including the run-off of prior years). The file is checked by cockpit.ingest first.
-- No KPI reads this table: a current-year ratio is not comparable with the company
-- loss ratio, so version 1 shows no market gap per line.
CREATE OR REPLACE TABLE ref_market_lob_gdv AS
SELECT
    year,
    line_group,
    gdv_line,
    loss_ratio_pct,
    ratio_type,
    basis,
    source,
    source_table,
    source_page
FROM read_csv(
    getvariable('reference_dir') || '/market_lob_gdv.csv',
    header = true,
    auto_detect = false,
    columns = {
        'year': 'INTEGER',
        'line_group': 'VARCHAR',
        'gdv_line': 'VARCHAR',
        'loss_ratio_pct': 'DECIMAL(6, 2)',
        'ratio_type': 'VARCHAR',
        'basis': 'VARCHAR',
        'source': 'VARCHAR',
        'source_table': 'VARCHAR',
        'source_page': 'INTEGER'
    }
)
ORDER BY year, line_group;
