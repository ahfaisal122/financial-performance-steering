"""Analysis views FR-1.12 to FR-1.16, against hand-calculated values.

Uses the small book described at the top of test_kpis.py. The loss ratio walk for
AGCS SE on that book, in percentage points:

    2024  Property   rate 0.60 x (50% - 60%) = -6.00   mix (0.6667 - 0.60) x 50% = +3.33
    2024  Liability  rate 0.40 x (75% - 80%) = -2.00   mix (0.3333 - 0.40) x 75% = -5.00
    2024  Total      68.00% to 58.33%, change -9.67 = -8.00 rate - 1.67 mix
    2025  Property   rate 0.6667 x (70% - 50%) = +13.33  mix 0 (shares unchanged)
    2025  Liability  rate 0.3333 x (80% - 75%) = +1.67   mix 0
    2025  Total      58.33% to 73.33%, change +15.00
"""

from __future__ import annotations

import pytest

from cockpit import pipeline
from cockpit.config import REPO_ROOT
from test_kpis import AGCS, AGCS_BOOK, HDI, HDI_YEAR, MARKET, build


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    books = {AGCS: AGCS_BOOK, HDI: {year: HDI_YEAR for year in (2023, 2024, 2025)}}
    connection = build(tmp_path_factory.mktemp("analysis_book"), books, MARKET)
    yield connection
    connection.close()


@pytest.fixture
def real(real_project, open_warehouse):
    pipeline.run(real_project)
    return open_warehouse(real_project)


def row(con, view: str, columns: str, year: int, line_group: str, insurer: str | None = AGCS):
    """One row of a view as a tuple; fails if the key does not give exactly one row."""
    where, params = "year = ? AND line_group = ?", [year, line_group]
    if insurer is not None:
        where, params = where + " AND insurer = ?", params + [insurer]
    rows = con.execute(f"SELECT {columns} FROM {view} WHERE {where}", params).fetchall()
    assert len(rows) == 1, f"{view}: {len(rows)} rows for {insurer} {year} {line_group}"
    return rows[0]


def test_views_do_not_depend_on_pipeline_settings():
    """A view is computed when it is read, for example by Power BI, without the pipeline."""
    for folder in ("30_marts", "40_analysis"):
        for path in (REPO_ROOT / "sql" / folder).glob("*.sql"):
            assert "getvariable" not in path.read_text(), path.name


# FR-1.12 year over year


def test_yoy_growth_and_loss_ratio_change(con):
    columns = "gwp_growth, loss_ratio_change_pts"
    assert row(con, "analysis_yoy", columns, 2024, "Property") == pytest.approx((0.125, -10.0))
    assert row(con, "analysis_yoy", columns, 2025, "Liability") == pytest.approx((0.25, 5.0))
    assert row(con, "analysis_yoy", columns, 2025, "Total") == pytest.approx(
        (1540 / 1340 - 1, 15.0)
    )


def test_yoy_leaves_out_the_first_year(con):
    assert con.execute("SELECT DISTINCT year FROM analysis_yoy ORDER BY year").fetchall() == [
        (2024,),
        (2025,),
    ]


def test_real_yoy_covers_2023_to_2025_for_both_insurers(real):
    rows = real.execute(
        "SELECT insurer, year, COUNT(gwp_growth), COUNT(loss_ratio_change_pts) "
        "FROM analysis_yoy WHERE line_group IN ('Property', 'Liability', 'Total') "
        "GROUP BY insurer, year ORDER BY insurer, year"
    ).fetchall()
    assert rows == [
        (insurer, year, 3, 3)
        for insurer in ("AGCS SE", "HDI Global SE")
        for year in (2023, 2024, 2025)
    ]


# FR-1.13 loss ratio walk


def test_walk_rate_and_mix_effect_per_line_group(con):
    columns = "rate_effect_pts, mix_effect_pts, total_effect_pts"
    view = "analysis_lr_walk"
    assert row(con, view, columns, 2024, "Property") == pytest.approx((-6.0, 10 / 3, -8 / 3))
    assert row(con, view, columns, 2024, "Liability") == pytest.approx((-2.0, -5.0, -7.0))
    assert row(con, view, columns, 2025, "Property") == pytest.approx(
        (40 / 3, 0.0, 40 / 3), abs=1e-9
    )
    assert row(con, view, columns, 2025, "Liability") == pytest.approx(
        (5 / 3, 0.0, 5 / 3), abs=1e-9
    )


def test_walk_total_row_sums_the_effects_and_matches_the_reported_change(con):
    columns = (
        "gross_loss_ratio_prior, gross_loss_ratio, rate_effect_pts, mix_effect_pts, "
        "total_effect_pts, check_gap_pts"
    )
    assert row(con, "analysis_lr_walk", columns, 2024, "Total") == pytest.approx(
        (0.68, 700 / 1200, -8.0, -5 / 3, -29 / 3, 0.0), abs=1e-9
    )
    assert row(con, "analysis_lr_walk", columns, 2025, "Total") == pytest.approx(
        (700 / 1200, 1100 / 1500, 15.0, 0.0, 15.0, 0.0), abs=1e-9
    )


def test_walk_line_group_that_enters_the_book_counts_as_mix(tmp_path):
    # 2024: Property only, 50 / 100 = 50%. 2025: Property 50 / 100, Liability 80 / 100: 65%.
    property_line = {"R0110": 100, "R0210": 100, "R0310": 50}
    liability_line = {"R0110": 100, "R0210": 100, "R0310": 80}
    books = {
        AGCS: {
            2024: {"C0070": property_line},
            2025: {"C0070": property_line, "C0080": liability_line},
        }
    }
    con = build(tmp_path, books)
    try:
        columns = "mix_share_prior, mix_share, rate_effect_pts, mix_effect_pts"
        # Property keeps its 50% loss ratio but halves its share: 0.5 x 50% - 1.0 x 50%.
        assert row(con, "analysis_lr_walk", columns, 2025, "Property") == pytest.approx(
            (1.0, 0.5, 0.0, -25.0)
        )
        # Liability is new: no prior loss ratio, so its 80 / 200 is all mix.
        assert row(con, "analysis_lr_walk", columns, 2025, "Liability") == pytest.approx(
            (0.0, 0.5, 0.0, 40.0)
        )
        assert row(
            con, "analysis_lr_walk", "total_effect_pts, check_gap_pts", 2025, "Total"
        ) == pytest.approx((15.0, 0.0), abs=1e-9)
    finally:
        con.close()


def test_real_walk_effects_sum_to_the_total_change_within_001_points(real):
    rows = real.execute(
        "SELECT insurer, year, check_gap_pts FROM analysis_lr_walk WHERE is_total "
        "ORDER BY insurer, year"
    ).fetchall()
    assert [(insurer, year) for insurer, year, _ in rows] == [
        (insurer, year) for insurer in ("AGCS SE", "HDI Global SE") for year in (2023, 2024, 2025)
    ]
    assert all(abs(gap) <= 0.01 for _, _, gap in rows), rows

    # The line group rows add up to the Total row.
    (worst,) = real.execute(
        """
        SELECT MAX(ABS(lines.effect - total.total_effect_pts))
        FROM (
            SELECT insurer, year, SUM(rate_effect_pts + mix_effect_pts) AS effect
            FROM analysis_lr_walk WHERE NOT is_total GROUP BY insurer, year
        ) AS lines
        INNER JOIN analysis_lr_walk AS total
            ON lines.insurer = total.insurer AND lines.year = total.year AND total.is_total
        """
    ).fetchone()
    assert worst < 1e-9


# FR-1.14 rolling average


def test_rolling_avg_and_gap_to_it(con):
    columns = "gross_loss_ratio, loss_ratio_3y_avg, gap_to_3y_avg_pts"
    assert row(con, "analysis_rolling_avg", columns, 2025, "Property") == pytest.approx(
        (0.70, 1460 / 2400, (0.70 - 1460 / 2400) * 100)
    )
    assert row(con, "analysis_rolling_avg", columns, 2024, "Property") == (
        pytest.approx(0.50),
        None,
        None,
    )


def test_real_rolling_avg_has_values_for_2024_and_2025(real):
    rows = real.execute(
        "SELECT insurer, year, COUNT(loss_ratio_3y_avg) FROM analysis_rolling_avg "
        "WHERE line_group IN ('Property', 'Liability', 'Total') "
        "GROUP BY insurer, year ORDER BY insurer, year"
    ).fetchall()
    assert rows == [
        (insurer, year, 3 if year >= 2024 else 0)
        for insurer in ("AGCS SE", "HDI Global SE")
        for year in (2022, 2023, 2024, 2025)
    ]


# FR-1.15 peer and market


def test_peer_market_total_row_shows_all_three_side_by_side(con):
    columns = (
        "focus_insurer, focus_loss_ratio, peer_insurer, peer_loss_ratio, market, "
        "market_loss_ratio, peer_gap_pts, focus_market_gap_pts, peer_market_gap_pts, "
        "peer_status, market_status"
    )
    got = row(con, "analysis_peer_market", columns, 2025, "Total", insurer=None)
    assert got == (
        AGCS,
        pytest.approx(1100 / 1500),
        HDI,
        pytest.approx(880 / 1200),
        "German market",
        pytest.approx(0.65),
        pytest.approx(0.0, abs=1e-9),
        pytest.approx((1100 / 1500 - 0.65) * 100),
        pytest.approx((880 / 1200 - 0.65) * 100),
        "ok",
        "ok",
    )


def test_peer_market_line_group_rows_have_a_peer_but_no_market(con):
    columns = "peer_gap_pts, market_loss_ratio, focus_market_gap_pts, market_status"
    got = row(con, "analysis_peer_market", columns, 2025, "Property", insurer=None)
    assert got == (pytest.approx(5.0), None, None, "no market data")


def test_peer_market_says_no_market_data_for_a_year_the_market_lacks(con):
    got = row(con, "analysis_peer_market", "market_loss_ratio, market_status", 2024, "Total", None)
    assert got == (None, "no market data")


def test_real_peer_market_total_has_all_three_for_every_year(real):
    rows = real.execute(
        "SELECT year, focus_loss_ratio IS NOT NULL, peer_loss_ratio IS NOT NULL, "
        "market_loss_ratio IS NOT NULL, market_status FROM analysis_peer_market "
        "WHERE is_total ORDER BY year"
    ).fetchall()
    assert rows == [(year, True, True, True, "ok") for year in (2022, 2023, 2024, 2025)]


# FR-1.16 flags


def flags(con) -> list[tuple]:
    return con.execute(
        "SELECT flag, insurer, year, line_group FROM analysis_flags ORDER BY ALL"
    ).fetchall()


def test_flag_loss_ratio_moved_more_than_5_points_and_sits_above_its_average(con):
    # Property 2025: +20 points, 70% against a 60.8% average. Total 2025: +15 points,
    # 73.3% against 67.0%. Liability 2025 moved exactly +5 points: not more than 5.
    assert flags(con) == [
        ("lr_move_above_3y_avg", AGCS, 2025, "Property"),
        ("lr_move_above_3y_avg", AGCS, 2025, "Total"),
    ]
    numbers = con.execute(
        "SELECT gross_loss_ratio, loss_ratio_change_pts, loss_ratio_3y_avg FROM analysis_flags "
        "WHERE line_group = 'Property'"
    ).fetchone()
    assert numbers == pytest.approx((0.70, 20.0, 1460 / 2400))


def test_flag_covers_a_move_down_that_still_sits_above_the_average(tmp_path):
    # Loss ratio 50%, 90%, 80%: 2025 moved -10 points, average 220 / 300 = 73.3%.
    def year(claims: int) -> dict:
        return {"C0070": {"R0110": 100, "R0210": 100, "R0310": claims}}

    con = build(tmp_path, {AGCS: {2023: year(50), 2024: year(90), 2025: year(80)}})
    try:
        rows = con.execute(
            "SELECT flag, year, line_group, loss_ratio_change_pts FROM analysis_flags "
            "WHERE line_group = 'Property'"
        ).fetchall()
    finally:
        con.close()
    assert rows == [("lr_move_above_3y_avg", 2025, "Property", pytest.approx(-10.0))]


def test_flag_peer_moved_the_other_way(tmp_path):
    def year(property_claims: int, liability_claims: int) -> dict:
        return {
            "C0070": {"R0110": 100, "R0210": 100, "R0310": property_claims},
            "C0080": {"R0110": 100, "R0210": 100, "R0310": liability_claims},
        }

    # Property: AGCS 50% to 60%, HDI 60% to 50%: opposite. Liability: both up 10 points.
    books = {
        AGCS: {2024: year(50, 50), 2025: year(60, 60)},
        HDI: {2024: year(60, 50), 2025: year(50, 60)},
    }
    con = build(tmp_path, books)
    try:
        rows = con.execute(
            "SELECT flag, insurer, year, line_group, loss_ratio_change_pts, peer_insurer, "
            "peer_loss_ratio_change_pts FROM analysis_flags"
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        (
            "peer_moved_other_way",
            AGCS,
            2025,
            "Property",
            pytest.approx(10.0),
            HDI,
            pytest.approx(-10.0),
        )
    ]


def test_flag_growth_slowed_for_two_years(tmp_path):
    def year(property_gwp: float, liability_gwp: float) -> dict:
        return {
            "C0070": {"R0110": property_gwp, "R0210": 100, "R0310": 50},
            "C0080": {"R0110": liability_gwp, "R0210": 100, "R0310": 50},
        }

    # Property grows 50%, 20%, 10%: slower twice. Liability grows 10%, 20%, 10%: not twice.
    books = {
        AGCS: {
            2022: year(100, 100),
            2023: year(150, 110),
            2024: year(180, 132),
            2025: year(198, 145),
        }
    }
    con = build(tmp_path, books)
    try:
        rows = con.execute(
            "SELECT flag, year, line_group, gwp_growth, gwp_growth_prior, "
            "gwp_growth_two_years_ago FROM analysis_flags WHERE line_group <> 'Total'"
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        (
            "growth_slowed_two_years",
            2025,
            "Property",
            pytest.approx(0.10),
            pytest.approx(0.20),
            pytest.approx(0.50),
        )
    ]


def test_real_flags_have_one_row_per_flag_and_the_numbers_behind_it(real):
    rows, keys = real.execute(
        "SELECT COUNT(*), COUNT(DISTINCT (flag, insurer, year, line_group)) FROM analysis_flags"
    ).fetchone()
    assert rows == keys
    assert rows > 0
    (incomplete,) = real.execute(
        """
        SELECT COUNT(*) FROM analysis_flags
        WHERE (flag = 'lr_move_above_3y_avg'
                AND (loss_ratio_change_pts IS NULL OR loss_ratio_3y_avg IS NULL))
            OR (flag = 'peer_moved_other_way'
                AND (loss_ratio_change_pts IS NULL OR peer_loss_ratio_change_pts IS NULL))
            OR (flag = 'growth_slowed_two_years'
                AND (gwp_growth IS NULL OR gwp_growth_two_years_ago IS NULL))
        """
    ).fetchone()
    assert incomplete == 0
