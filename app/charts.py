"""Charts of the dashboard, built with Altair.

One palette for every chart, in the navy-and-gold look of the app. A line group or
company keeps its color on every page and under every filter. The colors were checked
for colorblind safety on the white page. The gold has low contrast against white,
which is why every chart has its numbers in a table below it.
"""

from __future__ import annotations

from dataclasses import dataclass

import altair as alt
import pandas as pd

from queries import LINE_GROUPS

FONT = '-apple-system, BlinkMacSystemFont, "Helvetica Neue", "Segoe UI", Arial, sans-serif'


@dataclass(frozen=True)
class Theme:
    surface: str
    ink: str
    ink_secondary: str
    ink_muted: str
    grid: str
    axis: str
    categorical: tuple[str, ...]
    lowers: str  # an effect that lowers the loss ratio
    raises: str  # an effect that raises the loss ratio
    neutral: str  # context series, such as the 3-year average


THEME = Theme(
    surface="#ffffff",
    ink="#12305a",
    ink_secondary="#3b4757",
    ink_muted="#6b778a",
    grid="#e8ecf1",
    axis="#c9d1db",
    # navy, gold, teal, burgundy, violet, green
    categorical=("#2a5fa8", "#d08a12", "#109a8c", "#b8365c", "#8a63c8", "#4a8f20"),
    lowers="#2a5fa8",
    raises="#b8365c",
    neutral="#8a94a6",
)


def _finish(chart: alt.TopLevelMixin, theme: Theme) -> alt.TopLevelMixin:
    """Quiet chrome: no frame, hairline solid grid, muted axis text, legend on top."""
    return (
        chart.configure(background="transparent", font=FONT)
        .configure_view(stroke=None)
        .configure_axis(
            gridColor=theme.grid,
            gridWidth=1,
            domainColor=theme.axis,
            tickColor=theme.axis,
            labelColor=theme.ink_muted,
            titleColor=theme.ink_secondary,
            labelFontSize=12,
            titleFontSize=12,
            titleFontWeight="normal",
        )
        .configure_legend(
            orient="top",
            title=None,
            labelColor=theme.ink_secondary,
            labelFontSize=12,
            labelLimit=320,
            symbolSize=90,
        )
        .configure_header(
            title=None,
            labelColor=theme.ink,
            labelFontSize=13,
            labelFontWeight="bold",
            labelAnchor="start",
            labelPadding=6,
        )
    )


def _line_group_scale(theme: Theme) -> alt.Scale:
    return alt.Scale(domain=list(LINE_GROUPS), range=list(theme.categorical))


def waterfall(steps: pd.DataFrame, theme: Theme) -> alt.TopLevelMixin:
    """Loss ratio walk. `steps` has label, start, end, kind (level, raises, lowers), text.

    The two loss ratio levels are drawn as ticks, the effects as floating bars between
    them. A floating bar's length is the size of the effect, so the axis does not need
    to start at zero.
    """
    order = steps["label"].tolist()
    y = alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, ticks=False))
    low = min(steps["start"].min(), steps["end"].min())
    high = max(steps["start"].max(), steps["end"].max())
    pad = max((high - low) * 0.18, 0.5)
    x_scale = alt.Scale(domain=[low - pad, high + pad], nice=False, zero=False)
    x_axis = alt.Axis(title="Gross loss ratio, in %", format=".1f", tickCount=6)

    effects = steps[steps["kind"] != "level"]
    levels = steps[steps["kind"] == "level"]
    tooltip = [alt.Tooltip("label:N", title="Step"), alt.Tooltip("text:N", title="Value")]

    bars = (
        alt.Chart(effects)
        .mark_bar(size=18, cornerRadius=2)
        .encode(
            y=y,
            x=alt.X("start:Q", scale=x_scale, axis=x_axis),
            x2="end:Q",
            color=alt.Color(
                "kind:N",
                scale=alt.Scale(domain=["raises", "lowers"], range=[theme.raises, theme.lowers]),
                legend=alt.Legend(
                    labelExpr="datum.value == 'raises' ? 'Raises the loss ratio' "
                    ": 'Lowers the loss ratio'"
                ),
            ),
            tooltip=tooltip,
        )
    )
    ticks = (
        alt.Chart(levels)
        .mark_tick(thickness=3, size=26, color=theme.ink)
        .encode(y=y, x=alt.X("end:Q", scale=x_scale), tooltip=tooltip)
    )
    labels = (
        alt.Chart(steps)
        .transform_calculate(tip="max(datum.start, datum.end)")
        .mark_text(align="left", dx=6, fontSize=12, color=theme.ink_secondary)
        .encode(y=y, x=alt.X("tip:Q", scale=x_scale), text="text:N")
    )
    chart = (bars + ticks + labels).properties(height=alt.Step(34))
    return _finish(chart, theme)


def loss_ratio_small_multiples(trend: pd.DataFrame, theme: Theme) -> alt.TopLevelMixin:
    """Gross loss ratio and its 3-year average, one small chart per line group."""
    long = trend.melt(
        id_vars=["year", "line_group"],
        value_vars=["gross_loss_ratio", "loss_ratio_3y_avg"],
        var_name="series",
        value_name="ratio",
    ).dropna(subset=["ratio"])
    long["series"] = long["series"].map(
        {"gross_loss_ratio": "Gross loss ratio", "loss_ratio_3y_avg": "3-year average"}
    )
    groups = [group for group in LINE_GROUPS if group in set(long["line_group"])]
    color = alt.Color(
        "series:N",
        scale=alt.Scale(
            domain=["Gross loss ratio", "3-year average"],
            range=[theme.categorical[0], theme.neutral],
        ),
    )
    base = alt.Chart(long).encode(
        x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("ratio:Q", title=None, axis=alt.Axis(format=".0%", tickCount=4)),
        color=color,
        tooltip=[
            alt.Tooltip("line_group:N", title="Line group"),
            alt.Tooltip("year:O", title="Year"),
            alt.Tooltip("series:N", title="Series"),
            alt.Tooltip("ratio:Q", title="Value", format=".1%"),
        ],
    )
    lines = base.mark_line(strokeWidth=2, strokeCap="round", strokeJoin="round")
    points = base.mark_point(size=95, filled=True, opacity=1, stroke=theme.surface, strokeWidth=2)
    chart = (
        (lines + points)
        .properties(width=230, height=150)
        .facet(facet=alt.Facet("line_group:N", sort=groups), columns=min(3, len(groups)))
    )
    return _finish(chart, theme)


def gwp_small_multiples(trend: pd.DataFrame, theme: Theme) -> alt.TopLevelMixin:
    """Gross written premium by year, one small chart per line group, each on its own scale."""
    data = trend.assign(gwp_meur=trend["gwp_teur"].astype(float) / 1000)
    groups = [group for group in LINE_GROUPS if group in set(data["line_group"])]
    chart = (
        alt.Chart(data)
        .mark_bar(size=20, cornerRadiusEnd=4, color=theme.categorical[0])
        .encode(
            x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                "gwp_meur:Q", title=None, axis=alt.Axis(format=",.0f", tickCount=4, minExtent=42)
            ),
            tooltip=[
                alt.Tooltip("line_group:N", title="Line group"),
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("gwp_meur:Q", title="GWP, EUR m", format=",.1f"),
                alt.Tooltip("gwp_growth:Q", title="Growth", format="+.1%"),
            ],
        )
        .properties(width=230, height=130)
        .facet(facet=alt.Facet("line_group:N", sort=groups), columns=min(3, len(groups)))
        .resolve_scale(y="independent")
    )
    return _finish(chart, theme)


def mix_share_bars(mix: pd.DataFrame, theme: Theme) -> alt.TopLevelMixin:
    """Share of each line group in gross earned premium, one stacked bar per year."""
    data = mix.dropna(subset=["mix_share"]).copy()
    data["order"] = data["line_group"].map({group: i for i, group in enumerate(LINE_GROUPS)})
    chart = (
        alt.Chart(data)
        # The stroke in the surface color is the 2px gap between the segments.
        .mark_bar(size=22, stroke=theme.surface, strokeWidth=2)
        .encode(
            y=alt.Y("year:O", title=None, axis=alt.Axis(ticks=False)),
            x=alt.X(
                "mix_share:Q",
                title="Share of gross earned premium",
                stack="zero",
                scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(format=".0%"),
            ),
            color=alt.Color("line_group:N", scale=_line_group_scale(theme)),
            order=alt.Order("order:Q"),
            tooltip=[
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("line_group:N", title="Line group"),
                alt.Tooltip("mix_share:Q", title="Mix share", format=".1%"),
            ],
        )
        .properties(height=alt.Step(40))
    )
    return _finish(chart, theme)


def _series_scale(series: list[str], theme: Theme) -> alt.Scale:
    return alt.Scale(domain=series, range=list(theme.categorical[: len(series)]))


def total_trend_lines(long: pd.DataFrame, series: list[str], theme: Theme) -> alt.TopLevelMixin:
    """Total gross loss ratio over the years: the two companies and the market."""
    last_year = long["year"].max()
    base = alt.Chart(long).encode(
        x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(
            "ratio:Q",
            title="Gross loss ratio",
            scale=alt.Scale(zero=False, padding=12),
            axis=alt.Axis(format=".0%", tickCount=5),
        ),
        color=alt.Color("series:N", scale=_series_scale(series, theme)),
        tooltip=[
            alt.Tooltip("year:O", title="Year"),
            alt.Tooltip("series:N", title="Series"),
            alt.Tooltip("ratio:Q", title="Gross loss ratio", format=".1%"),
        ],
    )
    lines = base.mark_line(strokeWidth=2, strokeCap="round", strokeJoin="round")
    points = base.mark_point(size=95, filled=True, opacity=1, stroke=theme.surface, strokeWidth=2)
    end_labels = (
        alt.Chart(long[long["year"] == last_year])
        .mark_text(align="left", dx=9, fontSize=12, color=theme.ink_secondary)
        .encode(
            x="year:O",
            y="ratio:Q",
            text=alt.Text("ratio:Q", format=".1%"),
        )
    )
    chart = (lines + points + end_labels).properties(height=260)
    return _finish(chart, theme)


def movers_bars(movers: pd.DataFrame, theme: Theme) -> alt.TopLevelMixin:
    """The line groups whose loss ratio moved most, ranked, one bar per move from zero.

    `movers` has line_group, gross_loss_ratio_prior, gross_loss_ratio and
    loss_ratio_change_pts. A bar to the right raised the loss ratio (worse).
    """
    data = movers.copy()
    data["change"] = data["loss_ratio_change_pts"].astype(float)
    data["kind"] = data["change"].map(lambda v: "raises" if v >= 0 else "lowers")
    data["label"] = [
        f"{'▲' if c >= 0 else '▼'} {c:+.1f} pts  ({p:.1%} → {n:.1%})"
        for c, p, n in zip(
            data["change"], data["gross_loss_ratio_prior"], data["gross_loss_ratio"], strict=True
        )
    ]
    order = data["line_group"].tolist()
    reach = max(abs(data["change"].min()), abs(data["change"].max()), 1.0)
    # Room for the label on the side the bar points to.
    x_scale = alt.Scale(domain=[-reach * 1.8, reach * 1.8], nice=False)
    y = alt.Y("line_group:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, ticks=False))
    color = alt.Color(
        "kind:N",
        scale=alt.Scale(domain=["raises", "lowers"], range=[theme.raises, theme.lowers]),
        legend=alt.Legend(
            labelExpr="datum.value == 'raises' ? 'Loss ratio up (worse)' "
            ": 'Loss ratio down (better)'"
        ),
    )
    tooltip = [
        alt.Tooltip("line_group:N", title="Line group"),
        alt.Tooltip("label:N", title="Move"),
    ]
    bars = (
        alt.Chart(data)
        .mark_bar(size=22, cornerRadiusEnd=4)
        .encode(
            y=y,
            x=alt.X(
                "change:Q",
                scale=x_scale,
                title="Change in gross loss ratio, percentage points",
                axis=alt.Axis(format="+.0f", tickCount=6),
            ),
            color=color,
            tooltip=tooltip,
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"zero": [0.0]}))
        .mark_rule(color=theme.axis, strokeWidth=1)
        .encode(x=alt.X("zero:Q", scale=x_scale))
    )
    right = (
        alt.Chart(data[data["change"] >= 0])
        .mark_text(align="left", dx=6, fontSize=12, fontWeight="bold", color=theme.ink)
        .encode(y=y, x=alt.X("change:Q", scale=x_scale), text="label:N")
    )
    left = (
        alt.Chart(data[data["change"] < 0])
        .mark_text(align="right", dx=-6, fontSize=12, fontWeight="bold", color=theme.ink)
        .encode(y=y, x=alt.X("change:Q", scale=x_scale), text="label:N")
    )
    chart = (zero + bars + right + left).properties(height=alt.Step(44))
    return _finish(chart, theme)


# One hue from light to dark, for magnitude: the higher the loss ratio, the darker the cell.
SEQUENTIAL = ("#e8eff8", "#bcd0ea", "#86a9d6", "#4f7dbd", "#2a5fa8", "#12305a")


def loss_ratio_heatmap(trend: pd.DataFrame, theme: Theme) -> alt.TopLevelMixin:
    """Gross loss ratio per line group and year, the value written in each cell."""
    data = trend.dropna(subset=["gross_loss_ratio"]).copy()
    data["ratio"] = data["gross_loss_ratio"].astype(float)
    groups = [group for group in LINE_GROUPS if group in set(data["line_group"])]
    low, high = float(data["ratio"].min()), float(data["ratio"].max())
    middle = low + (high - low) * 0.55
    y = alt.Y("line_group:N", sort=groups, title=None, axis=alt.Axis(labelLimit=260, ticks=False))
    x = alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0, orient="top", ticks=False))
    cells = (
        alt.Chart(data)
        .mark_rect(cornerRadius=3, stroke=theme.surface, strokeWidth=3)
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "ratio:Q",
                scale=alt.Scale(domain=[low, high], range=list(SEQUENTIAL)),
                legend=alt.Legend(
                    title="Gross loss ratio", format=".0%", orient="right", gradientLength=160
                ),
            ),
            tooltip=[
                alt.Tooltip("line_group:N", title="Line group"),
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("ratio:Q", title="Gross loss ratio", format=".1%"),
                alt.Tooltip("loss_ratio_3y_avg:Q", title="3-year average", format=".1%"),
            ],
        )
    )
    text = (
        alt.Chart(data)
        .mark_text(fontSize=13, fontWeight="bold")
        .encode(
            x=x,
            y=y,
            text=alt.Text("ratio:Q", format=".1%"),
            color=alt.condition(
                alt.datum.ratio > middle, alt.value("#ffffff"), alt.value(theme.ink)
            ),
        )
    )
    chart = (cells + text).properties(height=alt.Step(44), width=alt.Step(110))
    return _finish(chart, theme).configure_legend(orient="right", title=None)


def peer_dumbbell(rows: pd.DataFrame, focus: str, peer: str, theme: Theme) -> alt.TopLevelMixin:
    """Focus company and peer per line group: two dots joined by a line, the gap at the end.

    `rows` has line_group, focus_loss_ratio, peer_loss_ratio, peer_gap_pts, peer_status,
    market_loss_ratio. The market appears on the total row only, as a grey diamond.
    """
    order = rows["line_group"].tolist()
    wide = rows.copy()
    for column in ("focus_loss_ratio", "peer_loss_ratio", "market_loss_ratio", "peer_gap_pts"):
        wide[column] = wide[column].astype(float)
    wide["gap_label"] = [
        (f"▼ {gap:+.1f} pts, lower" if gap < 0 else f"▲ {gap:+.1f} pts, higher")
        if status == "ok"
        else "no peer data"
        for gap, status in zip(wide["peer_gap_pts"], wide["peer_status"], strict=True)
    ]
    # The gap label sits right of the rightmost mark of the row, market diamond included.
    wide["label_at"] = wide[["focus_loss_ratio", "peer_loss_ratio", "market_loss_ratio"]].max(
        axis=1
    )
    dots = pd.concat(
        [
            pd.DataFrame(
                {
                    "line_group": wide["line_group"],
                    "series": focus,
                    "ratio": wide["focus_loss_ratio"],
                }
            ),
            pd.DataFrame(
                {"line_group": wide["line_group"], "series": peer, "ratio": wide["peer_loss_ratio"]}
            ),
            pd.DataFrame(
                {
                    "line_group": wide["line_group"],
                    "series": "German market",
                    "ratio": wide["market_loss_ratio"],
                }
            ),
        ]
    ).dropna(subset=["ratio"])
    series = [name for name in (focus, peer, "German market") if name in set(dots["series"])]
    high = float(dots["ratio"].max())
    low = float(dots["ratio"].min())
    pad = (high - low) * 0.25 + 0.02
    x_scale = alt.Scale(domain=[min(0.0, low - pad), high + pad * 1.6], nice=False, zero=False)
    y = alt.Y("line_group:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, ticks=False))
    links = (
        alt.Chart(wide.dropna(subset=["focus_loss_ratio", "peer_loss_ratio"]))
        .mark_rule(strokeWidth=4, strokeCap="round", color=theme.axis)
        .encode(
            y=y,
            x=alt.X(
                "focus_loss_ratio:Q",
                scale=x_scale,
                title="Gross loss ratio",
                axis=alt.Axis(format=".0%", tickCount=6),
            ),
            x2="peer_loss_ratio:Q",
        )
    )
    palette = {
        focus: theme.categorical[0],
        peer: theme.categorical[1],
        "German market": theme.neutral,
    }
    points = (
        alt.Chart(dots)
        .mark_point(filled=True, opacity=1, size=200, stroke=theme.surface, strokeWidth=2)
        .encode(
            y=y,
            x=alt.X("ratio:Q", scale=x_scale),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(domain=series, range=[palette[name] for name in series]),
                legend=alt.Legend(title=None),
            ),
            shape=alt.Shape(
                "series:N",
                scale=alt.Scale(
                    domain=series,
                    range=["circle" if name != "German market" else "diamond" for name in series],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("line_group:N", title="Line group"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("ratio:Q", title="Gross loss ratio", format=".1%"),
            ],
        )
    )
    gaps = (
        alt.Chart(wide.dropna(subset=["label_at"]))
        .mark_text(align="left", dx=14, fontSize=12, fontWeight="bold", color=theme.ink)
        .encode(y=y, x=alt.X("label_at:Q", scale=x_scale), text="gap_label:N")
    )
    chart = (links + points + gaps).properties(height=alt.Step(42))
    return _finish(chart, theme)


def market_bullet(bullet: pd.DataFrame, market: float, theme: Theme) -> alt.TopLevelMixin:
    """Each company's total loss ratio as a bar, the German market as a dark line across.

    `bullet` has series and ratio, in display order.
    """
    data = bullet.copy()
    data["ratio"] = data["ratio"].astype(float)
    order = data["series"].tolist()
    top = max(float(data["ratio"].max()), market) * 1.18
    x_scale = alt.Scale(domain=[0, top], nice=False)
    y = alt.Y(
        "series:N", sort=order, title=None, axis=alt.Axis(ticks=False, labelFontWeight="bold")
    )
    bars = (
        alt.Chart(data)
        .mark_bar(size=26, cornerRadiusEnd=4)
        .encode(
            y=y,
            x=alt.X(
                "ratio:Q",
                scale=x_scale,
                title="Total gross loss ratio",
                axis=alt.Axis(format=".0%", tickCount=6),
            ),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(domain=order, range=list(theme.categorical[: len(order)])),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("series:N", title="Company"),
                alt.Tooltip("ratio:Q", title="Gross loss ratio", format=".1%"),
            ],
        )
    )
    values = (
        alt.Chart(data)
        .mark_text(align="left", dx=6, fontSize=13, fontWeight="bold", color=theme.ink)
        .encode(y=y, x=alt.X("ratio:Q", scale=x_scale), text=alt.Text("ratio:Q", format=".1%"))
    )
    line = pd.DataFrame({"market": [market], "label": [f"German market {market:.1%}"]})
    rule = (
        alt.Chart(line)
        .mark_rule(color=theme.ink, strokeWidth=2, strokeDash=[6, 3])
        .encode(x=alt.X("market:Q", scale=x_scale))
    )
    rule_label = (
        alt.Chart(line)
        .mark_text(align="center", dy=-8, fontSize=12, color=theme.ink_secondary)
        .encode(x=alt.X("market:Q", scale=x_scale), y=alt.value(0), text="label:N")
    )
    chart = (bars + values + rule + rule_label).properties(height=alt.Step(48))
    return _finish(chart, theme)
