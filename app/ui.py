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
    """Chart colors for the theme the viewer has on. Light when it cannot be told."""
    try:
        mode = st.context.theme.type
    except Exception:
        mode = None
    return charts.theme_for(mode)


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
