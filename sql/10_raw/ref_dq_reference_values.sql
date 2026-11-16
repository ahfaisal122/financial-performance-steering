-- FR-1.5: figures printed elsewhere in the reports, typed in by hand.
CREATE OR REPLACE TABLE ref_dq_reference_values AS
SELECT insurer, year, metric, value_teur, source
FROM read_csv(
    getvariable('reference_dir') || '/dq_reference_values.csv',
    header = true,
    auto_detect = false,
    columns = {
        'insurer': 'VARCHAR',
        'year': 'INTEGER',
        'metric': 'VARCHAR',
        'value_teur': 'DECIMAL(18, 3)',
        'source': 'VARCHAR'
    }
)
ORDER BY insurer, year, metric;
