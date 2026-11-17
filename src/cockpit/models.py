"""Build the data model, the KPI views and the analysis views (FR-1.8 to FR-1.16).

One SQL file per model in sql/20_staging, sql/30_marts and sql/40_analysis, run in the order
below: a model comes after everything it reads from. The pipeline calls this
only after the quality gate has passed.
"""

from __future__ import annotations

import duckdb

from cockpit.config import Paths
from cockpit.db import run_sql_file

STAGING_MODELS: tuple[str, ...] = ("stg_eiopa_nonlife",)

MART_MODELS: tuple[str, ...] = (
    "dim_insurer",
    "dim_lob",
    "dim_metric",
    "dim_year",
    "fct_s050102",
    "mart_lob_year",
    "mart_line_group_year",
    "mart_market_year",
    "kpi_definitions",
    "kpi_gwp",
    "kpi_gep",
    "kpi_gross_claims",
    "kpi_gross_loss_ratio",
    "kpi_ceded_share",
    "kpi_net_loss_ratio",
    "kpi_net_expense_ratio",
    "kpi_gwp_growth",
    "kpi_loss_ratio_change",
    "kpi_loss_ratio_3y_avg",
    "kpi_mix_share",
    "kpi_peer_gap",
    "kpi_market_gap",
)


ANALYSIS_MODELS: tuple[str, ...] = (
    "analysis_yoy",
    "analysis_lr_walk",
    "analysis_rolling_avg",
    "analysis_peer_market",
    "analysis_flags",
)

MODEL_FOLDERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("20_staging", STAGING_MODELS),
    ("30_marts", MART_MODELS),
    ("40_analysis", ANALYSIS_MODELS),
)


class ModelError(Exception):
    """The model was built but breaks one of its own rules."""


def build_marts(con: duckdb.DuckDBPyConnection, paths: Paths) -> tuple[str, ...]:
    """Build every model, then check the rules the model must keep."""
    built: tuple[str, ...] = ()
    for folder, models in MODEL_FOLDERS:
        for name in models:
            run_sql_file(con, paths.sql_dir / folder / f"{name}.sql")
        built += models
    check_model(con)
    return built


def check_model(con: duckdb.DuckDBPyConnection) -> None:
    """Stop if a line has no line group, the fact table lost rows, joins or value,
    or the market table is empty."""
    unmapped = [
        code
        for (code,) in con.execute(
            "SELECT lob_code FROM dim_lob WHERE line_group IS NULL ORDER BY lob_code"
        ).fetchall()
    ]
    if unmapped:
        raise ModelError(
            "Column codes without a line group in data/reference/lob_groups.csv: "
            + ", ".join(unmapped)
        )

    (unjoined,) = con.execute(
        """
        SELECT COUNT(*)
        FROM fct_s050102 AS fct
        LEFT JOIN dim_insurer AS insurer ON fct.insurer = insurer.insurer
        LEFT JOIN dim_lob AS lob ON fct.lob_code = lob.lob_code
        LEFT JOIN dim_metric AS metric ON fct.row_code = metric.row_code
        LEFT JOIN dim_year AS year ON fct.year = year.year
        WHERE insurer.insurer IS NULL OR lob.lob_code IS NULL
            OR metric.row_code IS NULL OR year.year IS NULL
        """
    ).fetchone()
    if unjoined:
        raise ModelError(f"{unjoined} fact rows do not join to every dimension (FR-1.8).")

    (market_years,) = con.execute("SELECT COUNT(*) FROM mart_market_year").fetchone()
    if not market_years:
        raise ModelError(
            "mart_market_year is empty: raw_eiopa has no rows with business type 'Non-Life'."
        )

    raw_rows, raw_value, fct_rows, fct_value = con.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM raw_s050102),
            (SELECT SUM(value_teur) FROM raw_s050102),
            (SELECT COUNT(*) FROM fct_s050102),
            (SELECT SUM(value_teur) FROM fct_s050102)
        """
    ).fetchone()
    if (raw_rows, raw_value) != (fct_rows, fct_value):
        raise ModelError(
            f"fct_s050102 ({fct_rows} rows, {fct_value} TEUR) does not equal "
            f"raw_s050102 ({raw_rows} rows, {raw_value} TEUR) (FR-1.9)."
        )
