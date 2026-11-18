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


def peer_market_bars(
    long: pd.DataFrame, series: list[str], rows: list[str], theme: Theme
) -> alt.TopLevelMixin:
    """Gross loss ratio per line group, one bar per company and one for the market.

    `long` has line_group, series, ratio and label (the value as text, or the reason
    why there is none).
    """
    y = alt.Y("line_group:N", sort=rows, title=None, axis=alt.Axis(labelLimit=240, ticks=False))
    offset = alt.YOffset("series:N", sort=series)
    present = long.dropna(subset=["ratio"])
    low = min(0.0, float(present["ratio"].min()))
    # Room on the right for the value labels; the axis always includes zero.
    x_scale = alt.Scale(domain=[low, float(present["ratio"].max()) * 1.12], nice=True, zero=True)
    bars = (
        alt.Chart(present)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            y=y,
            yOffset=offset,
            x=alt.X(
                "ratio:Q",
                title="Gross loss ratio",
                scale=x_scale,
                axis=alt.Axis(format=".0%", tickCount=6),
            ),
            color=alt.Color("series:N", scale=_series_scale(series, theme)),
            tooltip=[
                alt.Tooltip("line_group:N", title="Line group"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("ratio:Q", title="Gross loss ratio", format=".1%"),
            ],
        )
    )
    baseline = (
        alt.Chart(pd.DataFrame({"zero": [0.0]}))
        .mark_rule(color=theme.axis, strokeWidth=1)
        .encode(x=alt.X("zero:Q", scale=x_scale))
    )
    labels = (
        alt.Chart(long)
        .transform_calculate(tip="isValid(datum.ratio) ? max(datum.ratio, 0) : 0")
        .mark_text(align="left", dx=5, fontSize=11, color=theme.ink_secondary)
        .encode(y=y, yOffset=offset, x=alt.X("tip:Q", scale=x_scale), text="label:N")
    )
    chart = (baseline + bars + labels).properties(height=alt.Step(17))
    return _finish(chart, theme)


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
