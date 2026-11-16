-- FR-1.9: the long fact table, one row per raw row, total column (C0200) included.
-- template and source_file stay on every row so a number traces back to its file (NFR-6).
CREATE OR REPLACE TABLE fct_s050102 AS
SELECT
    insurer,
    year,
    lob_code,
    row_code,
    value_teur,
    template,
    source_file
FROM raw_s050102
ORDER BY insurer, year, lob_code, row_code;
