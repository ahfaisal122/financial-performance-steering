-- FR-1.13: the loss ratio walk. The change in the total gross loss ratio from t-1 to t,
-- split per line group into a rate effect and a mix effect, in percentage points:
--   rate effect = mix share(t-1) x (LR(t) - LR(t-1))
--   mix effect  = (mix share(t) - mix share(t-1)) x LR(t)
-- A line group's part of the total loss ratio is its claims over the GEP of all lines.
-- The change in that part is the line group's total effect; the mix effect is the total
-- effect minus the rate effect, which equals the formula above. A line group without a
-- loss ratio in one of the two years has no rate effect: its whole effect counts as mix.
-- The Total row sums the effects and carries the reported loss ratios (C0200).
-- check_gap_pts is the summed effects minus the reported change; it must stay within 0.01.
CREATE OR REPLACE VIEW analysis_lr_walk AS
WITH line_year AS (
    SELECT
        mix.insurer,
        mix.year,
        mix.line_group,
        mix.mix_share,
        lr.gross_loss_ratio,
        CASE
            WHEN mix.gep_all_lines_teur > 0
                THEN COALESCE(lr.gross_claims_teur, 0)::DOUBLE / mix.gep_all_lines_teur::DOUBLE
        END AS lr_part
    FROM kpi_mix_share AS mix
    INNER JOIN kpi_gross_loss_ratio AS lr
        ON mix.insurer = lr.insurer AND mix.year = lr.year AND mix.line_group = lr.line_group
),

insurer_years AS (
    SELECT DISTINCT insurer, year FROM line_year
),

paired AS (
    SELECT
        COALESCE(cur.insurer, prior.insurer) AS insurer,
        COALESCE(cur.year, prior.year + 1) AS year,
        COALESCE(cur.line_group, prior.line_group) AS line_group,
        COALESCE(prior.mix_share, 0) AS mix_share_prior,
        COALESCE(cur.mix_share, 0) AS mix_share,
        prior.gross_loss_ratio AS gross_loss_ratio_prior,
        cur.gross_loss_ratio,
        COALESCE(prior.lr_part, 0) AS lr_part_prior,
        COALESCE(cur.lr_part, 0) AS lr_part
    FROM line_year AS cur
    FULL OUTER JOIN line_year AS prior
        ON cur.insurer = prior.insurer
        AND cur.line_group = prior.line_group
        AND cur.year - 1 = prior.year
),

effects AS (
    SELECT
        paired.*,
        CASE
            WHEN gross_loss_ratio IS NOT NULL AND gross_loss_ratio_prior IS NOT NULL
                THEN mix_share_prior * (gross_loss_ratio - gross_loss_ratio_prior) * 100
            ELSE 0
        END AS rate_effect_pts,
        (lr_part - lr_part_prior) * 100 AS total_effect_pts
    FROM paired
    -- Keep only steps where the insurer has both years.
    INNER JOIN insurer_years AS this_year
        ON paired.insurer = this_year.insurer AND paired.year = this_year.year
    INNER JOIN insurer_years AS prior_year
        ON paired.insurer = prior_year.insurer AND paired.year - 1 = prior_year.year
)

SELECT
    insurer,
    year,
    line_group,
    FALSE AS is_total,
    mix_share_prior,
    mix_share,
    gross_loss_ratio_prior,
    gross_loss_ratio,
    rate_effect_pts,
    total_effect_pts - rate_effect_pts AS mix_effect_pts,
    total_effect_pts,
    NULL::DOUBLE AS check_gap_pts
FROM effects
UNION ALL
SELECT
    effects.insurer,
    effects.year,
    'Total' AS line_group,
    TRUE AS is_total,
    SUM(effects.mix_share_prior) AS mix_share_prior,
    SUM(effects.mix_share) AS mix_share,
    reported.gross_loss_ratio_prior,
    reported.gross_loss_ratio,
    SUM(effects.rate_effect_pts) AS rate_effect_pts,
    SUM(effects.total_effect_pts - effects.rate_effect_pts) AS mix_effect_pts,
    SUM(effects.total_effect_pts) AS total_effect_pts,
    SUM(effects.total_effect_pts) - reported.loss_ratio_change_pts AS check_gap_pts
FROM effects
INNER JOIN kpi_loss_ratio_change AS reported
    ON effects.insurer = reported.insurer
    AND effects.year = reported.year
    AND reported.is_total
GROUP BY
    effects.insurer,
    effects.year,
    reported.gross_loss_ratio_prior,
    reported.gross_loss_ratio,
    reported.loss_ratio_change_pts;
