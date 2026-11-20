"""Peer and market page (FR-1.19): the focus company against the peer per line group,
and both against the German market at total level."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
import queries
import story
import ui

STATUS_TEXT = {"no peer data": "no peer data", "no focus data": "no own data"}


def render(slicers: ui.Slicers) -> None:
    st.title("Peer and market")
    st.caption(f"{slicers.year} · {slicers.level_label}")

    rows = queries.peer_market(slicers.year)
    if rows.empty:
        st.info("No comparison: the reference file names no focus company.")
        return
    focus, peer = rows.iloc[0]["focus_name"], rows.iloc[0]["peer_name"]
    ui.headline(story.peer(slicers.year, rows))
    ui.note(
        f"This page always compares {focus} with {peer}; the insurer filter does not apply. "
        "The German market exists at total level only, so line groups have no market bar."
    )

    order = [*queries.LINE_GROUPS, queries.TOTAL]
    rows = rows.assign(order=rows["line_group"].map({g: i for i, g in enumerate(order)}))
    rows = rows.sort_values("order")
    if slicers.line_group:
        rows = rows[rows["line_group"].isin([slicers.line_group, queries.TOTAL])]
    theme = ui.chart_theme()

    ui.section("Against the peer", f"Gross loss ratio by line group, {slicers.year}")
    st.altair_chart(charts.peer_dumbbell(rows, focus, peer, theme), width="stretch")
    ui.note(
        f"Each line joins {focus} and {peer}; the number at its end is the peer gap. "
        "The grey diamond is the German market, which exists at total level only."
    )
    ui.show_table(
        pd.DataFrame(
            {
                "Line group": rows["line_group"],
                focus: rows["focus_loss_ratio"].map(ui.pct),
                peer: [
                    ui.pct(ratio) if not ui.missing(ratio) else "no peer data"
                    for ratio in rows["peer_loss_ratio"]
                ],
                "Peer gap": [
                    ui.pts(gap) if status == "ok" else STATUS_TEXT.get(status, status)
                    for gap, status in zip(rows["peer_gap_pts"], rows["peer_status"], strict=True)
                ],
            }
        )
    )
    ui.note(
        f"The peer gap is the {focus} loss ratio minus the {peer} loss ratio, in percentage "
        f"points. A negative gap means {focus} is lower, which is better."
    )

    ui.section("Against the market", f"Against the German market, total {slicers.year}")
    total = rows[rows["line_group"] == queries.TOTAL].iloc[0]
    if total["market_status"] != "ok":
        st.info(f"No market comparison for {slicers.year}: {total['market_status']}.")
    else:
        market = ui.pct(total["market_loss_ratio"])
        tiles = st.columns(3)
        tiles[0].metric("German market, gross loss ratio", market, border=True, height="stretch")
        tiles[1].metric(
            f"{focus} against the market",
            ui.pts(total["focus_market_gap_pts"]),
            help=f"{focus} {ui.pct(total['focus_loss_ratio'])} minus the market {market}.",
            border=True,
            height="stretch",
        )
        tiles[2].metric(
            f"{peer} against the market",
            ui.pts(total["peer_market_gap_pts"]),
            help=f"{peer} {ui.pct(total['peer_loss_ratio'])} minus the market {market}.",
            border=True,
            height="stretch",
        )
        bullet = pd.DataFrame(
            {
                "series": [focus, peer],
                "ratio": [total["focus_loss_ratio"], total["peer_loss_ratio"]],
            }
        ).dropna(subset=["ratio"])
        st.altair_chart(
            charts.market_bullet(bullet, float(total["market_loss_ratio"]), theme),
            width="stretch",
        )
        ui.note("A negative value means the company's loss ratio is below the market's.")

    ui.section("Over time", "Total gross loss ratio, 2022 to 2025")
    trend = queries.peer_market_total_trend()
    names = {
        "focus_loss_ratio": trend.iloc[0]["focus_name"],
        "peer_loss_ratio": trend.iloc[0]["peer_name"],
        "market_loss_ratio": "German market",
    }
    trend_long = (
        trend.rename(columns=names)
        .melt(
            id_vars="year", value_vars=list(names.values()), var_name="series", value_name="ratio"
        )
        .dropna(subset=["ratio"])
    )
    trend_long["ratio"] = trend_long["ratio"].astype(float)
    trend_series = [name for name in names.values() if name in set(trend_long["series"])]
    st.altair_chart(charts.total_trend_lines(trend_long, trend_series, theme), width="stretch")
    ui.note(
        "The companies write business worldwide. The market is every non-life undertaking "
        "reporting in Germany, reinsurers included, so it is a reference point and not a "
        "like-for-like benchmark."
    )
    ui.table_view(
        pd.DataFrame(
            {"Year": trend["year"]}
            | {name: trend[column].map(ui.pct) for column, name in names.items()}
        )
    )
