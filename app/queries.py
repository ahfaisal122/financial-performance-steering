"""Read the warehouse for the dashboard.

Every function returns rows of one SQL view or table, filtered by the slicers.
The dashboard does no calculation of its own: a number on a page is a number in
a view. The warehouse is opened read-only.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from cockpit.config import Paths

TOTAL = "Total"
# Fixed display order of the line groups; a color follows its line group through every chart.
LINE_GROUPS = (
    "Property",
    "Liability",
    "Marine, aviation and transport",
    "Financial lines",
    "Motor",
    "Other",
)


def project_paths() -> Paths:
    """The project the dashboard reads. COCKPIT_ROOT points it at another folder (tests)."""
    root = os.environ.get("COCKPIT_ROOT")
    return Paths(root=Path(root)) if root else Paths()


def warehouse_exists() -> bool:
    return project_paths().warehouse.is_file()


@st.cache_data(show_spinner=False)
def _run(warehouse: str, modified: float, sql: str, params: tuple) -> pd.DataFrame:
    # `modified` is part of the cache key: a rebuilt warehouse is read again.
    con = duckdb.connect(warehouse, read_only=True)
    try:
        return con.execute(sql, list(params)).df()
    finally:
        con.close()


def query(sql: str, *params: object) -> pd.DataFrame:
    warehouse = project_paths().warehouse
    return _run(str(warehouse), warehouse.stat().st_mtime, sql, params)


# Slicer values


def insurers() -> pd.DataFrame:
    return query("SELECT insurer, insurer_short, role FROM dim_insurer ORDER BY role, insurer")


def years() -> list[int]:
    return query("SELECT year FROM dim_year ORDER BY year")["year"].tolist()


def line_groups() -> list[str]:
    present = set(query("SELECT DISTINCT line_group FROM mart_line_group_year")["line_group"])
    return [group for group in LINE_GROUPS if group in present]


# Overview


def headline(insurer: str, year: int, line_group: str) -> pd.DataFrame:
    """GWP, growth, gross loss ratio with its change, and ceded share for one level."""
    return query(
        """
        SELECT
            gwp.gwp_teur,
            growth.gwp_growth,
            change.gross_loss_ratio,
            change.loss_ratio_change_pts,
            ceded.ceded_share
        FROM kpi_gwp AS gwp
        INNER JOIN kpi_gwp_growth AS growth USING (insurer, year, line_group)
        INNER JOIN kpi_loss_ratio_change AS change USING (insurer, year, line_group)
        INNER JOIN kpi_ceded_share AS ceded USING (insurer, year, line_group)
        WHERE gwp.insurer = ? AND gwp.year = ? AND gwp.line_group = ?
        """,
        insurer,
        year,
        line_group,
    )


def lr_walk(insurer: str, year: int) -> pd.DataFrame:
    return query(
        """
        SELECT line_group, is_total, gross_loss_ratio_prior, gross_loss_ratio,
            rate_effect_pts, mix_effect_pts, total_effect_pts
        FROM analysis_lr_walk
        WHERE insurer = ? AND year = ?
        """,
        insurer,
        year,
    )


def top_movers(insurer: str, year: int, limit: int = 3) -> pd.DataFrame:
    """The line groups whose gross loss ratio moved most against the prior year."""
    return query(
        f"""
        SELECT line_group, gross_loss_ratio_prior, gross_loss_ratio, loss_ratio_change_pts
        FROM analysis_yoy
        WHERE insurer = ? AND year = ? AND NOT is_total AND loss_ratio_change_pts IS NOT NULL
        ORDER BY ABS(loss_ratio_change_pts) DESC, line_group
        LIMIT {int(limit)}
        """,
        insurer,
        year,
    )


# Line of business


def loss_ratio_trend(insurer: str) -> pd.DataFrame:
    return query(
        """
        SELECT year, line_group, gross_loss_ratio, loss_ratio_3y_avg, gap_to_3y_avg_pts
        FROM analysis_rolling_avg
        WHERE insurer = ? AND NOT is_total
        ORDER BY line_group, year
        """,
        insurer,
    )


def gwp_trend(insurer: str) -> pd.DataFrame:
    return query(
        """
        SELECT gwp.year, gwp.line_group, gwp.gwp_teur, growth.gwp_growth
        FROM kpi_gwp AS gwp
        INNER JOIN kpi_gwp_growth AS growth USING (insurer, year, line_group)
        WHERE gwp.insurer = ? AND NOT gwp.is_total
        ORDER BY gwp.line_group, gwp.year
        """,
        insurer,
    )


def mix_share(insurer: str) -> pd.DataFrame:
    return query(
        "SELECT year, line_group, gep_teur, mix_share FROM kpi_mix_share "
        "WHERE insurer = ? ORDER BY year, line_group",
        insurer,
    )


# Peer and market


def peer_market(year: int) -> pd.DataFrame:
    return query(
        """
        SELECT pm.line_group, pm.is_total, focus.insurer_short AS focus_name,
            pm.focus_loss_ratio, peer.insurer_short AS peer_name, pm.peer_loss_ratio,
            pm.market, pm.market_loss_ratio, pm.peer_gap_pts, pm.focus_market_gap_pts,
            pm.peer_market_gap_pts, pm.peer_status, pm.market_status
        FROM analysis_peer_market AS pm
        INNER JOIN dim_insurer AS focus ON pm.focus_insurer = focus.insurer
        LEFT JOIN dim_insurer AS peer ON pm.peer_insurer = peer.insurer
        WHERE pm.year = ?
        """,
        year,
    )


def peer_market_total_trend() -> pd.DataFrame:
    return query(
        """
        SELECT pm.year, focus.insurer_short AS focus_name, pm.focus_loss_ratio,
            peer.insurer_short AS peer_name, pm.peer_loss_ratio,
            pm.market, pm.market_loss_ratio
        FROM analysis_peer_market AS pm
        INNER JOIN dim_insurer AS focus ON pm.focus_insurer = focus.insurer
        LEFT JOIN dim_insurer AS peer ON pm.peer_insurer = peer.insurer
        WHERE pm.is_total
        ORDER BY pm.year
        """
    )


# Data quality and definitions

DQ_CHECKS = (
    ("FR-1.4", "dq_reconciliation", "Lines add up to the total column"),
    ("FR-1.5", "dq_reference_check", "GWP matches the printed reference values"),
    ("FR-1.6", "dq_net_check", "Gross minus reinsurers' share equals net"),
    ("FR-1.7", "dq_completeness", "Every year and main line is present"),
)


def dq_summary() -> pd.DataFrame:
    """One row per quality check with its row, fail and warning counts."""
    selects = [
        f"SELECT '{requirement}' AS requirement, '{table}' AS result_table, "
        f"COUNT(*) AS row_count, COUNT(*) FILTER (WHERE status = 'fail') AS failures, "
        f"COUNT(*) FILTER (WHERE status = 'warn') AS warnings FROM {table}"
        for requirement, table, _ in DQ_CHECKS
    ]
    summary = query(" UNION ALL ".join(selects) + " ORDER BY requirement")
    names = {table: description for _, table, description in DQ_CHECKS}
    return summary.assign(check_name=summary["result_table"].map(names))


def reconciliation(insurer: str, year: int) -> pd.DataFrame:
    return query(
        """
        SELECT row_code, line_count, sum_lines_teur, total_teur, gap_teur, status
        FROM dq_reconciliation
        WHERE insurer = ? AND year = ?
        ORDER BY ABS(gap_teur) DESC NULLS LAST, row_code
        """,
        insurer,
        year,
    )


def completeness() -> pd.DataFrame:
    return query(
        "SELECT check_type, insurer, year, line_group, status FROM dq_completeness "
        "ORDER BY insurer, year, line_group"
    )


def reference_check() -> pd.DataFrame:
    return query(
        "SELECT insurer, year, metric, reference_value_teur, pipeline_value_teur, gap_teur, "
        "status, source FROM dq_reference_check ORDER BY insurer, year"
    )


def source_files() -> pd.DataFrame:
    return query("SELECT source_file, row_count, loaded_at FROM raw_load_log ORDER BY source_file")


def kpi_definitions() -> pd.DataFrame:
    return query(
        "SELECT kpi_name, formula, unit, scope, caveat FROM kpi_definitions ORDER BY sort_order"
    )
