"""Overview page (FR-1.17): KPI cards, the loss ratio walk and the top 3 movers."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
import queries
import story
import ui


def _walk_steps(walk: pd.DataFrame, year: int) -> pd.DataFrame:
    """Lay the walk out as steps: prior loss ratio, rate effect per line group, mix, result."""
    total = walk[walk["is_total"]].iloc[0]
    lines = walk[~walk["is_total"]].set_index("line_group")
    position = float(total["gross_loss_ratio_prior"]) * 100
    steps = [
        {
            "label": f"{year - 1} loss ratio",
            "start": position,
            "end": position,
            "kind": "level",
            "text": f"{position:.1f}%",
        }
    ]
    effects = [
        (f"Rate: {group}", float(lines.loc[group, "rate_effect_pts"]))
        for group in queries.LINE_GROUPS
        if group in lines.index
    ]
    effects.append(("Mix: all line groups", float(total["mix_effect_pts"])))
    largest = max(effects, key=lambda item: abs(item[1]))[0] if effects else None
    for label, effect in effects:
        steps.append(
            {
                "label": label,
                "start": position,
                "end": position + effect,
                "kind": "raises" if effect >= 0 else "lowers",
                "text": f"{effect:+.2f} pts"
                + ("  ◀ largest effect" if label == largest and effect else ""),
            }
        )
        position += effect
    result = float(total["gross_loss_ratio"]) * 100
    steps.append(
        {
            "label": f"{year} loss ratio",
            "start": result,
            "end": result,
            "kind": "level",
            "text": f"{result:.1f}%",
        }
    )
    return pd.DataFrame(steps)


def render(slicers: ui.Slicers) -> None:
    st.title("Overview")
    st.caption(f"{slicers.insurer} · {slicers.year} · {slicers.level_label}")

    headline = queries.headline(slicers.insurer, slicers.year, slicers.level)
    walk = queries.lr_walk(slicers.insurer, slicers.year)
    driver = story.biggest_driver(walk) if slicers.line_group is None else None
    if headline.empty:
        st.info(f"{slicers.insurer} reports no figures for {slicers.level} in {slicers.year}.")
    else:
        ui.headline(story.performance(slicers.insurer, slicers.year, headline.iloc[0], driver))
        ui.kpi_cards(slicers, headline.iloc[0])

    ui.section("Why", "Why the loss ratio moved")
    if walk.empty:
        st.info(f"No walk for {slicers.year}: there is no prior year to compare with.")
    else:
        total = walk[walk["is_total"]].iloc[0]
        st.markdown(
            f"The company's gross loss ratio went from "
            f"**{ui.pct(total['gross_loss_ratio_prior'])}** to "
            f"**{ui.pct(total['gross_loss_ratio'])}** "
            f"({ui.pts(total['total_effect_pts'], 2)}): "
            f"**{ui.pts(total['rate_effect_pts'], 2)}** because line groups' own loss ratios "
            f"moved (rate), and **{ui.pts(total['mix_effect_pts'], 2)}** because the book "
            f"shifted between line groups (mix)."
        )
        st.altair_chart(
            charts.waterfall(_walk_steps(walk, slicers.year), ui.chart_theme()), width="stretch"
        )
        ui.note("The walk always shows the whole company; the line group filter does not apply.")
        detail = walk.assign(
            order=walk["line_group"].map(
                {group: i for i, group in enumerate((*queries.LINE_GROUPS, queries.TOTAL))}
            )
        ).sort_values("order")
        ui.table_view(
            pd.DataFrame(
                {
                    "Line group": detail["line_group"],
                    f"Loss ratio {slicers.year - 1}": detail["gross_loss_ratio_prior"].map(ui.pct),
                    f"Loss ratio {slicers.year}": detail["gross_loss_ratio"].map(ui.pct),
                    "Rate effect": detail["rate_effect_pts"].map(lambda v: ui.pts(v, 2)),
                    "Mix effect": detail["mix_effect_pts"].map(lambda v: ui.pts(v, 2)),
                    "Total effect": detail["total_effect_pts"].map(lambda v: ui.pts(v, 2)),
                }
            )
        )

    ui.section("Where", "Top 3 loss ratio movers")
    movers = queries.top_movers(slicers.insurer, slicers.year)
    if movers.empty:
        st.info(f"No movers for {slicers.year}: there is no prior year to compare with.")
    else:
        ui.note(
            f"The line groups whose gross loss ratio moved most against {slicers.year - 1}, "
            "in either direction."
        )
        st.altair_chart(charts.movers_bars(movers, ui.chart_theme()), width="stretch")
        ui.table_view(
            pd.DataFrame(
                {
                    "Line group": movers["line_group"],
                    f"Loss ratio {slicers.year - 1}": movers["gross_loss_ratio_prior"].map(ui.pct),
                    f"Loss ratio {slicers.year}": movers["gross_loss_ratio"].map(ui.pct),
                    "Change": movers["loss_ratio_change_pts"].map(ui.pts),
                }
            ),
            label="Show the movers as numbers",
        )
