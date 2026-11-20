"""Line of business page (FR-1.18): trend per line group, loss ratio against its
3-year average, and mix share."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
import queries
import story
import ui


def _only(table: pd.DataFrame, line_group: str | None) -> pd.DataFrame:
    return table if line_group is None else table[table["line_group"] == line_group]


def _against_average(gap: object) -> str:
    """Above or below the 3-year average, as an arrow and a word."""
    if ui.missing(gap):
        return "n/a"
    if round(float(gap), 1) == 0:
        return "■ at average"
    return "▲ above (worse)" if float(gap) > 0 else "▼ below (better)"


def render(slicers: ui.Slicers) -> None:
    st.title("Line of business")
    st.caption(f"{slicers.insurer} · 2022 to 2025 · {slicers.level_label}")
    theme = ui.chart_theme()

    loss_ratio = _only(queries.loss_ratio_trend(slicers.insurer), slicers.line_group)
    gwp = _only(queries.gwp_trend(slicers.insurer), slicers.line_group)
    mix = queries.mix_share(slicers.insurer)

    if loss_ratio.empty and gwp.empty:
        st.info(f"{slicers.insurer} reports no figures for {slicers.level_label}.")
        return

    year_view = loss_ratio[loss_ratio["year"] == slicers.year]
    ui.headline(story.line_of_business(slicers.year, year_view))

    if loss_ratio["gross_loss_ratio"].notna().any():
        ui.section("Where it hurts", "Gross loss ratio by line group and year")
        st.altair_chart(charts.loss_ratio_heatmap(loss_ratio, theme))
        ui.note(
            "The darker the cell, the higher the loss ratio. Hover a cell for its 3-year average."
        )

    ui.section("Against its own history", "Gross loss ratio against its 3-year average")
    ui.note(
        "The 3-year average is earned-weighted over the year and the two years before, "
        "so it exists for 2024 and 2025 only. All charts share one scale."
    )
    if loss_ratio["gross_loss_ratio"].notna().any():
        st.altair_chart(charts.loss_ratio_small_multiples(loss_ratio, theme))
    else:
        st.info("No loss ratio: there is no earned premium in any year.")

    ui.section("Growth", "Gross written premium, EUR m")
    ui.note("Each line group has its own scale, so read the shape, not the height across charts.")
    st.altair_chart(charts.gwp_small_multiples(gwp, theme))

    ui.section("Shape of the book", "Mix share")
    ui.note(
        "Each line group's share of the company's gross earned premium. "
        "The line group filter does not apply: a share needs the whole book."
    )
    st.altair_chart(charts.mix_share_bars(mix, theme), width="stretch")

    st.subheader(f"The numbers for {slicers.year}")
    year_rows = (
        gwp[gwp["year"] == slicers.year]
        .merge(
            loss_ratio[loss_ratio["year"] == slicers.year], on=["year", "line_group"], how="outer"
        )
        .merge(mix[mix["year"] == slicers.year], on=["year", "line_group"], how="left")
    )
    order = {group: i for i, group in enumerate(queries.LINE_GROUPS)}
    year_rows = year_rows.assign(order=year_rows["line_group"].map(order)).sort_values("order")
    ui.show_table(
        pd.DataFrame(
            {
                "Line group": year_rows["line_group"],
                "GWP, EUR m": year_rows["gwp_teur"].map(ui.meur),
                "GWP growth": year_rows["gwp_growth"].map(ui.signed_pct),
                "Gross loss ratio": year_rows["gross_loss_ratio"].map(ui.pct),
                "3-year average": year_rows["loss_ratio_3y_avg"].map(ui.pct),
                "Gap to average": year_rows["gap_to_3y_avg_pts"].map(ui.pts),
                "Against average": year_rows["gap_to_3y_avg_pts"].map(_against_average),
                "Mix share": year_rows["mix_share"].map(ui.pct),
            }
        )
    )

    all_years = loss_ratio.merge(gwp, on=["year", "line_group"], how="outer").merge(
        mix, on=["year", "line_group"], how="left"
    )
    ui.table_view(
        pd.DataFrame(
            {
                "Line group": all_years["line_group"],
                "Year": all_years["year"],
                "GWP, EUR m": all_years["gwp_teur"].map(ui.meur),
                "GWP growth": all_years["gwp_growth"].map(ui.signed_pct),
                "Gross loss ratio": all_years["gross_loss_ratio"].map(ui.pct),
                "3-year average": all_years["loss_ratio_3y_avg"].map(ui.pct),
                "Mix share": all_years["mix_share"].map(ui.pct),
            }
        ).sort_values(["Line group", "Year"]),
        label="Show the numbers for all years",
    )
