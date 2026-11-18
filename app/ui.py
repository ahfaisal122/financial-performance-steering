"""Pieces every page shares: slicers, number formats, table views and the footer."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

import charts
import queries

ALL_LINE_GROUPS = "All line groups"

HGB_NOTE = (
    "Figures follow German local GAAP (HGB), as published in the Solvency and Financial "
    "Condition Reports, template S.05.01.02. They differ from the IFRS 17 figures the groups "
    "publish. Amounts are in EUR, converted from EUR thousand as reported."
)
SOURCE_NOTE = (
    "Sources: public SFCR reports of AGCS SE and HDI Global SE, 2022 to 2025; "
    "EIOPA insurance statistics for the German non-life market."
)


@dataclass(frozen=True)
class Slicers:
    insurer: str
    insurer_short: str
    year: int
    line_group: str | None  # None means all line groups

    @property
    def level(self) -> str:
        """The row a headline number is read from: one line group, or the company total."""
        return self.line_group or queries.TOTAL

    @property
    def level_label(self) -> str:
        return self.line_group or "all line groups"


def sidebar_slicers() -> Slicers:
    """Insurer, year and line group. They sit in the sidebar and apply to every page."""
    insurers = queries.insurers()
    names = insurers["insurer"].tolist()
    short = dict(zip(insurers["insurer"], insurers["insurer_short"], strict=True))
    focus = insurers.loc[insurers["role"] == "focus", "insurer"]
    years = queries.years()
    groups = [ALL_LINE_GROUPS, *queries.line_groups()]

    with st.sidebar:
        st.subheader("Filters")
        insurer = st.selectbox(
            "Insurer",
            names,
            index=names.index(focus.iloc[0]) if len(focus) else 0,
            key="slicer_insurer",
        )
        year = st.selectbox("Year", years, index=len(years) - 1, key="slicer_year")
        group = st.selectbox("Line group", groups, key="slicer_line_group")
    return Slicers(
        insurer=insurer,
        insurer_short=short[insurer],
        year=int(year),
        line_group=None if group == ALL_LINE_GROUPS else group,
    )


def chart_theme() -> charts.Theme:
    return charts.THEME


STYLE = """
<style>
/* Page title: navy with a thin gold rule under it. */
[data-testid="stMainBlockContainer"] h1 {
    color: #12305a;
    letter-spacing: -0.01em;
    border-bottom: 2px solid #c9a227;
    padding-bottom: 0.45rem;
    margin-bottom: 0.2rem;
}
[data-testid="stMainBlockContainer"] h2,
[data-testid="stMainBlockContainer"] h3 {
    color: #12305a;
}
/* KPI cards: white, hairline border, navy top edge, small uppercase label. */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #dde3ea;
    border-top: 3px solid #12305a;
    border-radius: 4px;
    padding: 0.85rem 1rem 0.9rem 1rem;
    box-shadow: 0 1px 2px rgba(18, 48, 90, 0.06);
}
[data-testid="stMetricLabel"] p {
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.72rem;
    font-weight: 600;
    color: #5a6678;
}
[data-testid="stMetricValue"] {
    color: #12305a;
}
/* Tables: aligned figures. */
[data-testid="stDataFrame"] {
    font-variant-numeric: tabular-nums;
}
/* Expanders and bordered containers: the same hairline as the cards. */
[data-testid="stExpander"] details {
    border-color: #dde3ea;
    border-radius: 4px;
}
/* Sidebar brand block. */
.cockpit-brand {
    padding: 0.2rem 0 1.1rem 0;
    margin-bottom: 0.6rem;
    border-bottom: 1px solid #2c4c78;
}
.cockpit-brand .name {
    color: #d4af37;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}
.cockpit-brand .scope {
    color: #b8c6d9;
    font-size: 0.8rem;
    margin-top: 0.25rem;
    line-height: 1.35;
}
</style>
"""

BRAND = """
<div class="cockpit-brand">
  <div class="name">Steering cockpit</div>
  <div class="scope">Commercial P&amp;C · Solvency II S.05.01.02 · HGB basis</div>
</div>
"""


def apply_style() -> None:
    """The institutional look on top of the theme in .streamlit/config.toml."""
    st.html(STYLE)
    with st.sidebar:
        st.html(BRAND)


# Number formats. A missing value is shown as "n/a", never as zero.


def missing(value: object) -> bool:
    return value is None or pd.isna(value)


def pct(value: object, digits: int = 1) -> str:
    return "n/a" if missing(value) else f"{float(value):.{digits}%}"


def signed_pct(value: object, digits: int = 1) -> str:
    return "n/a" if missing(value) else f"{float(value):+.{digits}%}"


def pts(value: object, digits: int = 1) -> str:
    return "n/a" if missing(value) else f"{float(value):+.{digits}f} pts"


def meur(teur: object, digits: int = 1) -> str:
    """EUR thousand shown as EUR million."""
    return "n/a" if missing(teur) else f"{float(teur) / 1000:,.{digits}f}"


def show_table(table: pd.DataFrame, height: int | str = "auto") -> None:
    """A table across the page, with a first column wide enough for the longest line group."""
    first = table.columns[0]
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height=height,
        column_config={first: st.column_config.Column(width=250)},
    )


def table_view(table: pd.DataFrame, label: str = "Show the numbers") -> None:
    """The table twin of a chart: every plotted value, readable without hovering."""
    with st.expander(label):
        show_table(table)


def footer() -> None:
    st.divider()
    st.caption(HGB_NOTE)
    st.caption(SOURCE_NOTE)
