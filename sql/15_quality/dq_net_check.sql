-- FR-1.6: gross minus reinsurers' share must equal net, for written premium,
-- earned premium and claims, per insurer, year and column.
-- status: ok or warn (gap above the tolerance). A warning does not stop the run.
CREATE OR REPLACE TABLE dq_net_check AS
WITH blocks (block, gross_rows, ceded_row, net_row) AS (
    VALUES
    ('written', ['R0110', 'R0120', 'R0130'], 'R0140', 'R0200'),
    ('earned', ['R0210', 'R0220', 'R0230'], 'R0240', 'R0300'),
    ('claims', ['R0310', 'R0320', 'R0330'], 'R0340', 'R0400')
),

by_block AS (
    SELECT
        raw.insurer,
        raw.year,
        raw.lob_code,
        blocks.block,
        SUM(raw.value_teur) FILTER (WHERE list_contains(blocks.gross_rows, raw.row_code))
            AS gross_teur,
        SUM(raw.value_teur) FILTER (WHERE raw.row_code = blocks.ceded_row) AS ceded_teur,
        SUM(raw.value_teur) FILTER (WHERE raw.row_code = blocks.net_row) AS net_teur
    FROM raw_s050102 AS raw
    INNER JOIN blocks
        ON list_contains(blocks.gross_rows, raw.row_code)
        OR raw.row_code IN (blocks.ceded_row, blocks.net_row)
    GROUP BY raw.insurer, raw.year, raw.lob_code, blocks.block
),

with_gap AS (
    SELECT
        *,
        COALESCE(gross_teur, 0) - COALESCE(ceded_teur, 0) - COALESCE(net_teur, 0) AS gap_teur
    FROM by_block
)

SELECT
    insurer,
    year,
    lob_code,
    block,
    gross_teur,
    ceded_teur,
    net_teur,
    gap_teur,
    CASE WHEN ABS(gap_teur) <= getvariable('dq_tolerance_teur') THEN 'ok' ELSE 'warn' END
        AS status
FROM with_gap
ORDER BY insurer, year, lob_code, block;
