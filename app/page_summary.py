"""Executive summary page: the three questions on one screen.

How did we do? Why? What should we look at? Each block reads the same SQL views as
the detail pages; the headline sentence puts their values into words.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
import queries
import story
import ui

RED_FLAGS = {"lr_move_above_3y_avg", "peer_moved_other_way"}


def summary_walk_steps(total: pd.Series, year: int) -> pd.DataFrame:
    """The walk in four steps: last year, all rate effects together, mix, this year."""
    prior = float(total["gross_loss_ratio_prior"]) * 100
    rate = float(total["rate_effect_pts"])
    mix = float(total["mix_effect_pts"])
    result = float(total["gross_loss_ratio"]) * 100
    return pd.DataFrame(
        [
            {
                "label": f"{year - 1} loss ratio",
                "start": prior,
                "end": prior,
                "kind": "level",
                "text": f"{prior:.1f}%",
            },
            {
                "label": "Rate: line groups' own ratios",
                "start": prior,
                "end": prior + rate,
                "kind": "raises" if rate >= 0 else "lowers",
                "text": f"{rate:+.2f} pts",
            },
            {
                "label": "Mix: shift between line groups",
                "start": prior + rate,
                "end": prior + rate + mix,
                "kind": "raises" if mix >= 0 else "lowers",
                "text": f"{mix:+.2f} pts",
            },
            {
                "label": f"{year} loss ratio",
                "start": result,
                "end": result,
                "kind": "level",
                "text": f"{result:.1f}%",
            },
        ]
    )


def _flag_cards(flags: pd.DataFrame) -> None:
    """One callout per line group, with each of its flags as an icon, a title and the numbers."""
    groups = flags.assign(
        order=flags["line_group"].map(
            {g: i for i, g in enumerate((queries.TOTAL, *queries.LINE_GROUPS))}
        )
    ).sort_values("order")
    names = groups["line_group"].drop_duplicates().tolist()
    columns = st.columns(min(3, len(names)))
    for i, name in enumerate(names):
        rows = groups[groups["line_group"] == name]
        severity = "red" if rows["flag"].isin(RED_FLAGS).any() else "amber"
        with columns[i % len(columns)].container(key=f"flag_{severity}_{i}"):
            st.markdown(f"**{'Company total' if name == queries.TOTAL else name}**")
            for _, flag in rows.iterrows():
                red = flag["flag"] in RED_FLAGS
                st.badge(
                    story.FLAG_TITLES.get(flag["flag"], flag["flag"]),
                    icon=":material/error:" if red else ":material/warning:",
                    color="red" if red else "orange",
                )
                st.caption(story.flag_detail(flag))


def render(slicers: ui.Slicers) -> None:
    st.title("Executive summary")
    st.caption(f"{slicers.insurer} · {slicers.year} · {slicers.level_label}")

    headline = queries.headline(slicers.insurer, slicers.year, slicers.level)
    walk = queries.lr_walk(slicers.insurer, slicers.year)
    driver = story.biggest_driver(walk) if slicers.line_group is None else None

    if headline.empty:
        st.info(f"{slicers.insurer} reports no figures for {slicers.level} in {slicers.year}.")
    else:
        row = headline.iloc[0]
        ui.headline(story.performance(slicers.insurer, slicers.year, row, driver))
        ui.section("How did we do", "Key figures")
        ui.kpi_cards(slicers, row)

    ui.section("Why", "What moved the loss ratio")
    if walk.empty:
        st.info(f"No walk for {slicers.year}: there is no prior year to compare with.")
    else:
        total = walk[walk["is_total"]].iloc[0]
        st.markdown(
            f"Line groups' own loss ratios moved it by **{ui.pts(total['rate_effect_pts'], 2)}**, "
            f"the shift in the book between line groups by "
            f"**{ui.pts(total['mix_effect_pts'], 2)}**."
            + (
                f" The largest single effect: **{driver[0]}** ({ui.pts(driver[1], 2)})."
                if driver
                else ""
            )
        )
        st.altair_chart(
            charts.waterfall(summary_walk_steps(total, slicers.year), ui.chart_theme()),
            width="stretch",
        )
        ui.note("Whole company. The Overview page splits the rate effect by line group.")

    ui.section("What to look at", f"Flags for {slicers.year}")
    flags = queries.flags(slicers.insurer, slicers.year)
    if slicers.line_group:
        flags = flags[flags["line_group"] == slicers.line_group]
    if flags.empty:
        st.success(
            f"No flags for {slicers.insurer} in {slicers.year}: no line group crossed a rule.",
            icon=":material/check_circle:",
        )
    else:
        ui.note(
            "Fixed rules: a loss ratio move of more than 5 pts that sits above the 3-year "
            "average or runs against the peer, and premium growth that slowed two years running."
        )
        _flag_cards(flags)
