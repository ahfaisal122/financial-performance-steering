"""Pieces every page shares: slicers, number formats, table views and the footer."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import pandas as pd
import streamlit as st

import charts
import queries

ALL_LINE_GROUPS = "All line groups"
PRESENTATION_KEY = "presentation_mode"

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
        st.divider()
        st.toggle(
            "Presentation mode",
            key=PRESENTATION_KEY,
            help="Hides the detail tables and the method notes, and enlarges the headlines "
            "and the numbers, for showing the cockpit on a shared screen.",
        )
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
/* Masthead: a navy band with the key figures of the selection, like a market strip. */
.cockpit-masthead {
    background: linear-gradient(100deg, #0f2747 0%, #163a6b 100%);
    border-radius: 6px;
    border-bottom: 3px solid #c9a227;
    padding: 0.8rem 1.2rem 0.85rem 1.2rem;
    margin-bottom: 0.4rem;
    color: #e8eef6;
}
.cockpit-masthead .kicker {
    color: #d4af37;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.55rem;
}
.cockpit-masthead .strip {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 2.2rem;
}
.cockpit-masthead .item .label {
    color: #9fb3cc;
    font-size: 0.68rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.cockpit-masthead .item .value {
    color: #ffffff;
    font-size: 1.15rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
}
.cockpit-masthead .chip {
    display: inline-block;
    font-size: 0.74rem;
    font-weight: 600;
    padding: 0.05rem 0.4rem;
    border-radius: 3px;
    margin-left: 0.35rem;
    vertical-align: 0.15rem;
}
.cockpit-masthead .chip.good { background: #1e7a46; color: #ffffff; }
.cockpit-masthead .chip.bad { background: #b8365c; color: #ffffff; }
.cockpit-masthead .chip.flat { background: #3b5578; color: #e8eef6; }
/* Headline: the one sentence a page says, set large beside a gold rule. */
.st-key-headline {
    background: #f6f8fb;
    border-left: 4px solid #c9a227;
    border-radius: 0 4px 4px 0;
    padding: 0.85rem 1.1rem;
}
.st-key-headline p {
    font-size: 1.28rem;
    line-height: 1.45;
    color: #12305a;
    margin: 0;
}
/* Section kicker: the question a block answers, above its heading. */
.cockpit-kicker {
    color: #a8841a;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 0.9rem 0 -0.6rem 0;
}
/* KPI card: a bordered container holding a metric with its trend line and a peer badge. */
[class*="st-key-kpi_"] {
    background: #ffffff;
    border: 1px solid #dde3ea;
    border-top: 3px solid #12305a;
    border-radius: 4px;
    padding: 0.85rem 1rem 0.8rem 1rem;
    box-shadow: 0 1px 2px rgba(18, 48, 90, 0.06);
}
[class*="st-key-kpi_"] [data-testid="stMetric"] {
    border: none;
    box-shadow: none;
    padding: 0;
    background: transparent;
}
[class*="st-key-kpi_"] [data-testid="stMetricValue"] {
    font-size: 2.1rem;
}
/* Flag callouts: a colored edge for the kind of flag, with an icon and a word inside. */
[class*="st-key-flag_"] {
    background: #ffffff;
    border: 1px solid #dde3ea;
    border-radius: 4px;
    padding: 0.75rem 1rem;
}
[class*="st-key-flag_red_"] { border-left: 4px solid #b8365c; }
[class*="st-key-flag_amber_"] { border-left: 4px solid #b8761b; }
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


PRESENTATION_STYLE = """
<style>
/* Presentation mode: larger type, no method notes, no detail tables. */
[data-testid="stMainBlockContainer"] h1 { font-size: 2.6rem; }
[data-testid="stMainBlockContainer"] h3 { font-size: 1.45rem; }
.st-key-headline p { font-size: 1.6rem; }
[data-testid="stMetricValue"] { font-size: 2.5rem; }
[data-testid="stMainBlockContainer"] [data-testid="stExpander"] { display: none; }
.cockpit-masthead .item .value { font-size: 1.4rem; }
</style>
"""


def presenting() -> bool:
    return bool(st.session_state.get(PRESENTATION_KEY, False))


def apply_style() -> None:
    """The institutional look on top of the theme in .streamlit/config.toml."""
    st.html(STYLE)
    with st.sidebar:
        st.html(BRAND)


def apply_presentation_style() -> None:
    """Called after the slicers, once the toggle has its value."""
    if presenting():
        st.html(PRESENTATION_STYLE)


def note(text: str) -> None:
    """A method note under a chart. Hidden in presentation mode, where the speaker says it."""
    if not presenting():
        st.caption(text)


def headline(text: str | None) -> None:
    """The one sentence a page says, set large at the top."""
    if text:
        with st.container(key="headline"):
            st.markdown(text)


def section(kicker: str, title: str) -> None:
    """A block heading with the question it answers above it."""
    st.html(f'<div class="cockpit-kicker">{escape(kicker)}</div>')
    st.subheader(title)


def counterpart(insurer: str) -> tuple[str, str] | None:
    """The other company of the comparison: the peer for the focus company, and back."""
    others = queries.insurers()
    others = others[others["insurer"] != insurer]
    if others.empty:
        return None
    first = others.iloc[0]
    return first["insurer"], first["insurer_short"]


def _chip(text: str, good: bool | None) -> str:
    kind = "flat" if good is None else ("good" if good else "bad")
    return f'<span class="chip {kind}">{escape(text)}</span>'


def _arrow(value: float) -> str:
    return "▲" if value > 0 else ("▼" if value < 0 else "■")


def masthead(slicers: Slicers) -> None:
    """The navy band over every page: the key figures of the selection in one strip."""
    row = queries.headline(slicers.insurer, slicers.year, slicers.level)
    items: list[str] = []
    if not row.empty:
        r = row.iloc[0]
        growth = r["gwp_growth"]
        change = r["loss_ratio_change_pts"]
        growth_chip = (
            ""
            if missing(growth)
            else _chip(f"{_arrow(float(growth))} {signed_pct(growth)}", float(growth) > 0)
        )
        change_chip = (
            ""
            if missing(change)
            else _chip(
                f"{_arrow(float(change))} {pts(change)}",
                None if round(float(change), 1) == 0 else float(change) < 0,
            )
        )
        items += [
            ("GWP, EUR m", meur(r["gwp_teur"]) + growth_chip),
            ("Gross loss ratio", pct(r["gross_loss_ratio"]) + change_chip),
            ("Ceded share", pct(r["ceded_share"])),
        ]
    peers = queries.peer_market(slicers.year)
    totals = peers[peers["line_group"] == queries.TOTAL]
    if not totals.empty and totals.iloc[0]["market_status"] == "ok":
        items.append(("German market loss ratio", pct(totals.iloc[0]["market_loss_ratio"])))
    other = counterpart(slicers.insurer)
    if other:
        other_row = queries.headline(other[0], slicers.year, slicers.level)
        if not other_row.empty:
            items.append((f"{other[1]} loss ratio", pct(other_row.iloc[0]["gross_loss_ratio"])))
    strip = "".join(
        f'<div class="item"><div class="label">{escape(label)}</div>'
        f'<div class="value">{value}</div></div>'
        for label, value in items
    )
    kicker = f"{slicers.insurer} · FY {slicers.year} · {slicers.level_label} · HGB basis"
    st.html(
        f'<div class="cockpit-masthead"><div class="kicker">{escape(kicker)}</div>'
        f'<div class="strip">{strip}</div></div>'
    )


def kpi_cards(slicers: Slicers, row: pd.Series) -> None:
    """Four KPI tiles: the value, the change against last year, a trend line over the
    years and the same figure for the other company."""
    history = queries.kpi_history(slicers.insurer, slicers.level)
    other = counterpart(slicers.insurer)
    other_row = queries.headline(other[0], slicers.year, slicers.level) if other else pd.DataFrame()
    other_values = other_row.iloc[0] if not other_row.empty else None
    prior = f"against {slicers.year - 1}"

    def trend(column: str, scale: float = 1.0) -> list[float] | None:
        values = history[column].dropna().astype(float) * scale
        return values.round(4).tolist() if len(values) >= 2 else None

    def peer_badge(column: str, fmt, lower_is_better: bool | None = None) -> None:
        if other_values is None or missing(other_values[column]):
            return
        text = f"{other[1]} {fmt(other_values[column])}"
        color = "gray"
        if lower_is_better is not None and not missing(row[column]):
            own, theirs = float(row[column]), float(other_values[column])
            if own != theirs:
                color = "green" if (own < theirs) == lower_is_better else "red"
        st.badge(text, icon=":material/compare_arrows:", color=color)

    years = f"Trend {int(history['year'].min())} to {int(history['year'].max())}"
    cards = st.columns(4)
    with cards[0].container(key="kpi_gwp", height="stretch"):
        st.metric(
            "GWP, EUR m",
            meur(row["gwp_teur"]),
            help=f"Gross written premium in EUR million. {years}.",
            chart_data=trend("gwp_teur", 1 / 1000),
            chart_type="line",
        )
        peer_badge("gwp_teur", meur)
    with cards[1].container(key="kpi_growth", height="stretch"):
        st.metric(
            "GWP growth",
            signed_pct(row["gwp_growth"]),
            help=f"Gross written premium {prior}. HGB basis, currency effects included. {years}.",
            chart_data=trend("gwp_growth"),
            chart_type="line",
        )
        peer_badge("gwp_growth", signed_pct, lower_is_better=False)
    with cards[2].container(key="kpi_loss_ratio", height="stretch"):
        st.metric(
            "Gross loss ratio",
            pct(row["gross_loss_ratio"]),
            delta=None
            if missing(row["loss_ratio_change_pts"])
            else f"{pts(row['loss_ratio_change_pts'])} {prior}",
            delta_color="inverse",
            help=f"Gross claims incurred over gross earned premium. Lower is better. {years}.",
            chart_data=trend("gross_loss_ratio"),
            chart_type="line",
        )
        peer_badge("gross_loss_ratio", pct, lower_is_better=True)
    with cards[3].container(key="kpi_ceded", height="stretch"):
        st.metric(
            "Ceded share",
            pct(row["ceded_share"]),
            help=f"Reinsurers' share of gross written premium. {years}.",
            chart_data=trend("ceded_share"),
            chart_type="area",
        )
        peer_badge("ceded_share", pct)


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
