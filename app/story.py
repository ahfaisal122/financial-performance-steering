"""Headline sentences: the numbers of the views, put into words.

A page opens with one sentence that says what its numbers mean, so the page can be
presented by reading it. Nothing here calculates a new figure: every number in a
sentence is a value of a SQL view. The functions only pick which value to name
(for example the largest effect) and choose the verb from its sign.
"""

from __future__ import annotations

import pandas as pd

import queries
import ui

FLAG_TITLES = {
    "lr_move_above_3y_avg": "Above 3-year average",
    "peer_moved_other_way": "Against the peer",
    "growth_slowed_two_years": "Growth slowing",
}


def _size(value: object, digits: int = 1) -> str:
    """The size of a move without its sign, for sentences that say the direction in words."""
    return f"{abs(float(value)):.{digits}f} pts"


def _share(value: object) -> str:
    return f"{abs(float(value)):.1%}"


def biggest_driver(walk: pd.DataFrame) -> tuple[str, float] | None:
    """The step of the loss ratio walk with the largest effect: one line group's rate, or mix."""
    if walk.empty:
        return None
    total = walk[walk["is_total"]].iloc[0]
    lines = walk[~walk["is_total"]].dropna(subset=["rate_effect_pts"])
    candidates = [(row["line_group"], float(row["rate_effect_pts"])) for _, row in lines.iterrows()]
    if not ui.missing(total["mix_effect_pts"]):
        candidates.append(("the shift in mix", float(total["mix_effect_pts"])))
    if not candidates:
        return None
    return max(candidates, key=lambda item: abs(item[1]))


def loss_ratio_phrase(ratio: object, change: object) -> str:
    if ui.missing(ratio):
        return "no gross loss ratio"
    if ui.missing(change):
        return f"gross loss ratio at **{ui.pct(ratio)}**"
    change = float(change)
    if round(change, 1) == 0:
        return f"gross loss ratio unchanged at **{ui.pct(ratio)}**"
    verb = "improved" if change < 0 else "worsened"
    return f"gross loss ratio **{verb} {_size(change)}** to **{ui.pct(ratio)}**"


def premium_phrase(gwp_teur: object, growth: object) -> str:
    if ui.missing(gwp_teur):
        return "no premium"
    if ui.missing(growth):
        return f"premium of **EUR {ui.meur(gwp_teur)} m**"
    verb = "grew" if float(growth) >= 0 else "fell"
    return f"premium {verb} **{_share(growth)}** to **EUR {ui.meur(gwp_teur)} m**"


def performance(subject: str, year: int, row: pd.Series, driver: tuple[str, float] | None) -> str:
    """How did we do, and the main reason: the headline of the summary and the overview."""
    sentence = f"{subject}, {year}: " + loss_ratio_phrase(
        row["gross_loss_ratio"], row["loss_ratio_change_pts"]
    )
    if driver and not ui.missing(row["loss_ratio_change_pts"]):
        name, effect = driver
        sentence += f", driven mostly by {name} ({ui.pts(effect, 2)})"
    sentence += "; " + premium_phrase(row["gwp_teur"], row["gwp_growth"]) + "."
    if ui.missing(row["loss_ratio_change_pts"]):
        sentence += f" There is no {year - 1} to compare with."
    return sentence


def line_of_business(year: int, rows: pd.DataFrame) -> str | None:
    """Where the loss ratio is highest, and which line groups run above their 3-year average."""
    present = rows.dropna(subset=["gross_loss_ratio"])
    if present.empty:
        return None
    highest = present.loc[present["gross_loss_ratio"].astype(float).idxmax()]
    sentence = (
        f"In {year} the highest gross loss ratio is in **{highest['line_group']}** "
        f"at **{ui.pct(highest['gross_loss_ratio'])}**."
    )
    with_average = present.dropna(subset=["gap_to_3y_avg_pts"])
    if with_average.empty:
        return sentence + f" There is no 3-year average for {year} yet."
    above = with_average[with_average["gap_to_3y_avg_pts"] > 0]["line_group"].tolist()
    if above:
        return sentence + " Above their 3-year average: **" + ", ".join(above) + "**."
    return sentence + " Every line group is at or below its 3-year average."


def peer(year: int, rows: pd.DataFrame) -> str | None:
    """Where the focus company stands against the peer and the market, at total level."""
    totals = rows[rows["line_group"] == queries.TOTAL]
    if totals.empty:
        return None
    total = totals.iloc[0]
    focus, other = total["focus_name"], total["peer_name"]
    sentence = ""
    if total["peer_status"] == "ok":
        gap = float(total["peer_gap_pts"])
        side = "below" if gap < 0 else "above"
        sentence = (
            f"In {year} {focus} runs a total gross loss ratio **{_size(gap)} {side}** {other} "
            f"({ui.pct(total['focus_loss_ratio'])} against {ui.pct(total['peer_loss_ratio'])})."
        )
    lines = rows[(rows["line_group"] != queries.TOTAL) & (rows["peer_status"] == "ok")]
    better = lines[lines["peer_gap_pts"] < 0]["line_group"].tolist()
    worse = lines[lines["peer_gap_pts"] > 0]["line_group"].tolist()
    if better:
        sentence += f" Lower than {other} in **" + ", ".join(better) + "**."
    if worse:
        sentence += " Higher in **" + ", ".join(worse) + "**."
    if total["market_status"] == "ok":
        gap = float(total["focus_market_gap_pts"])
        side = "below" if gap < 0 else "above"
        sentence += (
            f" Against the German market ({ui.pct(total['market_loss_ratio'])}), {focus} "
            f"is **{_size(gap)} {side}**."
        )
    return sentence.strip() or None


def flag_detail(flag: pd.Series) -> str:
    """The numbers behind one flag, in one line."""
    kind = flag["flag"]
    if kind == "lr_move_above_3y_avg":
        verb = "rose" if flag["loss_ratio_change_pts"] > 0 else "fell"
        return (
            f"Loss ratio {verb} {_size(flag['loss_ratio_change_pts'])} to "
            f"{ui.pct(flag['gross_loss_ratio'])}, above its 3-year average of "
            f"{ui.pct(flag['loss_ratio_3y_avg'])}."
        )
    if kind == "peer_moved_other_way":
        verb = "rose" if flag["loss_ratio_change_pts"] > 0 else "fell"
        other = "fell" if verb == "rose" else "rose"
        return (
            f"Loss ratio {verb} {_size(flag['loss_ratio_change_pts'])}; "
            f"{flag['peer_name']}'s {other} {_size(flag['peer_loss_ratio_change_pts'])}."
        )
    if kind == "growth_slowed_two_years":
        return (
            "Premium growth "
            f"{ui.signed_pct(flag['gwp_growth_two_years_ago'])} → "
            f"{ui.signed_pct(flag['gwp_growth_prior'])} → {ui.signed_pct(flag['gwp_growth'])}."
        )
    return kind
