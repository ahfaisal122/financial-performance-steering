-- FR-1.8: one row per S.05.01.02 column code in the raw data, C0200 (total) included.
-- line_group comes from reference/lob_groups.csv; a code without a group stops the run.
-- If a code ever carries two spellings of a name, the first in alphabetical order is kept.
CREATE OR REPLACE TABLE dim_lob AS
SELECT
    raw.lob_code,
    MIN(raw.lob_name_de) AS lob_name_de,
    MIN(raw.lob_name_en) AS lob_name_en,
    ref.line_group,
    MIN(raw.business_type) AS business_type,
    raw.lob_code = 'C0200' AS is_total
FROM raw_s050102 AS raw
LEFT JOIN ref_lob_groups AS ref ON raw.lob_code = ref.lob_code
GROUP BY raw.lob_code, ref.line_group
ORDER BY raw.lob_code;
