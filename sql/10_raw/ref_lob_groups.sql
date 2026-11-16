-- Line groups per S.05.01.02 column code (requirements section 4).
-- is_main_line marks the groups the completeness check expects every year.
CREATE OR REPLACE TABLE ref_lob_groups AS
SELECT lob_code, line_group, is_main_line
FROM read_csv(
    getvariable('reference_dir') || '/lob_groups.csv',
    header = true,
    auto_detect = false,
    columns = {'lob_code': 'VARCHAR', 'line_group': 'VARCHAR', 'is_main_line': 'BOOLEAN'}
)
ORDER BY lob_code;
