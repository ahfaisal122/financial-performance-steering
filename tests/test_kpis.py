"""FR-1.11: one test per KPI against a hand-calculated value.

The book below is small enough to check on paper. AGCS SE is the focus company,
HDI Global SE the peer. Property is two columns (C0070 and C0160) so the tests
also cover a line group built from more than one column and a GWP built from
all three rows (R0110, R0120, R0130).

AGCS SE, line group level (EUR thousand):

    year  line group   GWP   GEP  claims  ceded written  net earned  net claims  expenses
    2023  Property     800   600     360            200         480         300       128
    2023  Liability    400   400     320            100         300         240        60
    2023  Total       1200  1000     680            300         780         540       188
    2024  Property     900   800     400
    2024  Liability    440   400     300
    2024  Total       1340  1200     700
    2025  Property     990  1000     700
    2025  Liability    550   500     400
    2025  Total       1540  1500    1100

HDI Global SE, every year: Property GEP 800, claims 520; Liability GEP 400, claims 360.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from cockpit import pipeline
from cockpit.config import Paths
from cockpit.db import connect
from conftest import market_rows, new_project, write_eiopa_file, write_sfcr_file

AGCS = "AGCS SE"
HDI = "HDI Global SE"

AGCS_BOOK = {
    2023: {
        "C0070": {
            "R0110": 500, "R0120": 100, "R0140": 150, "R0200": 450,
            "R0210": 450, "R0220": 50, "R0240": 100, "R0300": 400,
            "R0310": 250, "R0320": 50, "R0340": 60, "R0400": 240,
            "R0550": 120,
        },
        "C0160": {
            "R0130": 200, "R0140": 50, "R0200": 150,
            "R0230": 100, "R0240": 20, "R0300": 80,
            "R0330": 60, "R0340": 0, "R0400": 60,
            "R0550": 8,
        },
        "C0080": {
            "R0110": 400, "R0140": 100, "R0200": 300,
            "R0210": 400, "R0240": 100, "R0300": 300,
            "R0310": 320, "R0340": 80, "R0400": 240,
            "R0550": 60,
        },
    },
    2024: {
        "C0070": {
            "R0110": 900, "R0140": 180, "R0200": 720,
            "R0210": 800, "R0240": 160, "R0300": 640,
            "R0310": 400, "R0340": 80, "R0400": 320,
            "R0550": 160,
        },
        "C0080": {
            "R0110": 440, "R0140": 110, "R0200": 330,
            "R0210": 400, "R0240": 100, "R0300": 300,
            "R0310": 300, "R0340": 75, "R0400": 225,
            "R0550": 60,
        },
    },
    2025: {
        "C0070": {
            "R0110": 990, "R0140": 198, "R0200": 792,
            "R0210": 1000, "R0240": 200, "R0300": 800,
            "R0310": 700, "R0340": 140, "R0400": 560,
            "R0550": 200,
        },
        "C0080": {
            "R0110": 550, "R0140": 110, "R0200": 440,
            "R0210": 500, "R0240": 100, "R0300": 400,
            "R0310": 400, "R0340": 80, "R0400": 320,
            "R0550": 100,
        },
    },
}  # fmt: skip

HDI_YEAR = {
    "C0070": {
        "R0110": 800, "R0140": 0, "R0200": 800,
        "R0210": 800, "R0240": 0, "R0300": 800,
        "R0310": 520, "R0340": 0, "R0400": 520,
        "R0550": 80,
    },
    "C0080": {
        "R0110": 400, "R0140": 0, "R0200": 400,
        "R0210": 400, "R0240": 0, "R0300": 400,
        "R0310": 360, "R0340": 0, "R0400": 360,
        "R0550": 40,
    },
}  # fmt: skip


def write_company_year(paths: Paths, insurer: str, year: int, lines: dict) -> None:
    """Write the lines of one company-year and a total column that adds them up."""
    rows = [(lob, row, value) for lob, values in lines.items() for row, value in values.items()]
    totals: dict[str, int] = defaultdict(int)
    for _lob, row, value in rows:
        totals[row] += value
    rows += [("C0200", row, value) for row, value in totals.items()]
    write_sfcr_file(paths, insurer, year, rows)


def build(tmp_path, books: dict[str, dict[int, dict]], market: list | None = None):
    """Build a project from {insurer: {year: lines}} and return an open connection."""
    paths = new_project(tmp_path)
    if market is not None:
        write_eiopa_file(paths, market)
    for insurer, years in books.items():
        for year, lines in years.items():
            write_company_year(paths, insurer, year, lines)
    pipeline.run(paths)
    return connect(paths.warehouse)


# German market: 2023 loss ratio 700 / 1000 = 70%, 2025 loss ratio 650 / 1000 = 65%, no 2024.
MARKET = market_rows("GERMANY", 2023, earned=(700, 200, 100), claims=(500, 150, 50)) + market_rows(
    "GERMANY", 2025, earned=(600, 300, 100), claims=(400, 200, 50)
)


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    books = {AGCS: AGCS_BOOK, HDI: {year: HDI_YEAR for year in (2023, 2024, 2025)}}
    connection = build(tmp_path_factory.mktemp("kpi_book"), books, MARKET)
    yield connection
    connection.close()


def value(con, view: str, column: str, year: int, line_group: str, insurer: str = AGCS):
    """One KPI value; fails if the view has no single row for the key."""
    rows = con.execute(
        f"SELECT {column} FROM {view} WHERE insurer = ? AND year = ? AND line_group = ?",
        [insurer, year, line_group],
    ).fetchall()
    assert len(rows) == 1, f"{view}: {len(rows)} rows for {insurer} {year} {line_group}"
    return rows[0][0]


def test_gwp(con):
    assert value(con, "kpi_gwp", "gwp_teur", 2023, "Property") == 800  # 500 + 100 + 200
    assert value(con, "kpi_gwp", "gwp_teur", 2023, "Liability") == 400
    assert value(con, "kpi_gwp", "gwp_teur", 2023, "Total") == 1200


def test_gep(con):
    assert value(con, "kpi_gep", "gep_teur", 2023, "Property") == 600  # 450 + 50 + 100
    assert value(con, "kpi_gep", "gep_teur", 2023, "Total") == 1000


def test_gross_claims(con):
    assert value(con, "kpi_gross_claims", "gross_claims_teur", 2023, "Property") == 360
    assert value(con, "kpi_gross_claims", "gross_claims_teur", 2023, "Total") == 680


def test_gross_loss_ratio(con):
    view, column = "kpi_gross_loss_ratio", "gross_loss_ratio"
    assert value(con, view, column, 2023, "Property") == pytest.approx(0.60)  # 360 / 600
    assert value(con, view, column, 2023, "Liability") == pytest.approx(0.80)  # 320 / 400
    assert value(con, view, column, 2023, "Total") == pytest.approx(0.68)  # 680 / 1000


def test_ceded_share(con):
    view, column = "kpi_ceded_share", "ceded_share"
    assert value(con, view, column, 2023, "Property") == pytest.approx(0.25)  # 200 / 800
    assert value(con, view, column, 2023, "Total") == pytest.approx(0.25)  # 300 / 1200
    assert value(con, view, column, 2024, "Property") == pytest.approx(0.20)  # 180 / 900


def test_net_loss_ratio(con):
    view, column = "kpi_net_loss_ratio", "net_loss_ratio"
    assert value(con, view, column, 2023, "Property") == pytest.approx(0.625)  # 300 / 480
    assert value(con, view, column, 2023, "Total") == pytest.approx(540 / 780)


def test_net_expense_ratio(con):
    view, column = "kpi_net_expense_ratio", "net_expense_ratio"
    assert value(con, view, column, 2023, "Property") == pytest.approx(128 / 480)
    assert value(con, view, column, 2023, "Liability") == pytest.approx(0.20)  # 60 / 300


def test_gwp_growth(con):
    view, column = "kpi_gwp_growth", "gwp_growth"
    assert value(con, view, column, 2024, "Property") == pytest.approx(0.125)  # 900 / 800 - 1
    assert value(con, view, column, 2025, "Liability") == pytest.approx(0.25)  # 550 / 440 - 1
    assert value(con, view, column, 2024, "Total") == pytest.approx(1340 / 1200 - 1)
    assert value(con, view, column, 2023, "Property") is None  # no 2022


def test_loss_ratio_change(con):
    view, column = "kpi_loss_ratio_change", "loss_ratio_change_pts"
    assert value(con, view, column, 2024, "Property") == pytest.approx(-10.0)  # 50% - 60%
    assert value(con, view, column, 2025, "Property") == pytest.approx(20.0)  # 70% - 50%
    assert value(con, view, column, 2025, "Liability") == pytest.approx(5.0)  # 80% - 75%
    assert value(con, view, column, 2023, "Property") is None  # no 2022


def test_loss_ratio_3y_avg(con):
    view, column = "kpi_loss_ratio_3y_avg", "loss_ratio_3y_avg"
    # Earned-weighted: (360 + 400 + 700) / (600 + 800 + 1000), not the mean of 60%, 50%, 70%.
    assert value(con, view, column, 2025, "Property") == pytest.approx(1460 / 2400)
    assert value(con, view, column, 2025, "Property") != pytest.approx(0.60)
    assert value(con, view, column, 2025, "Liability") == pytest.approx(1020 / 1300)
    assert value(con, view, column, 2025, "Total") == pytest.approx(2480 / 3700)
    assert value(con, view, column, 2024, "Property") is None  # only two years


def test_mix_share(con):
    view, column = "kpi_mix_share", "mix_share"
    assert value(con, view, column, 2023, "Property") == pytest.approx(0.60)  # 600 / 1000
    assert value(con, view, column, 2023, "Liability") == pytest.approx(0.40)
    assert value(con, view, column, 2024, "Property") == pytest.approx(800 / 1200)
    (total_rows,) = con.execute(
        "SELECT COUNT(*) FROM kpi_mix_share WHERE line_group = 'Total'"
    ).fetchone()
    assert total_rows == 0


def test_peer_gap(con):
    gaps = {
        (year, line_group): gap
        for year, line_group, gap in con.execute(
            "SELECT year, line_group, peer_gap_pts FROM kpi_peer_gap "
            "WHERE focus_insurer = ? AND peer_insurer = ?",
            [AGCS, HDI],
        ).fetchall()
    }
    assert gaps[(2025, "Property")] == pytest.approx(5.0)  # 70% - 65%
    assert gaps[(2025, "Liability")] == pytest.approx(-10.0)  # 80% - 90%
    assert gaps[(2023, "Property")] == pytest.approx(-5.0)  # 60% - 65%
    assert gaps[(2025, "Total")] == pytest.approx((1100 / 1500 - 880 / 1200) * 100)
    assert len(gaps) == 9  # 3 years x (2 line groups + Total)
    assert con.execute("SELECT DISTINCT peer_status FROM kpi_peer_gap").fetchall() == [("ok",)]


def test_peer_gap_says_no_peer_data_when_the_peer_has_no_loss_ratio(tmp_path):
    # The peer reports Liability with zero premium and zero claims, and no Property at all.
    focus = {
        "C0070": {"R0110": 100, "R0210": 100, "R0310": 60},
        "C0080": {"R0110": 100, "R0210": 100, "R0310": 80},
        "C0120": {"R0110": 0, "R0210": 0, "R0310": 0},
    }
    peer = {
        "C0060": {"R0110": 100, "R0210": 100, "R0310": 50},
        "C0080": {"R0110": 0, "R0210": 0, "R0310": 0},
        "C0120": {"R0110": 100, "R0210": 100, "R0310": 50},
    }
    con = build(tmp_path, {AGCS: {2025: focus}, HDI: {2025: peer}})
    try:
        rows = con.execute(
            "SELECT line_group, peer_gap_pts, peer_status FROM kpi_peer_gap ORDER BY line_group"
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        ("Financial lines", None, "no focus data"),
        ("Liability", None, "no peer data"),
        ("Property", None, "no peer data"),
        ("Total", pytest.approx((140 / 200 - 100 / 200) * 100), "ok"),
    ]


def test_market_gap(con):
    view = "kpi_market_gap"
    # AGCS total 2025: 1100 / 1500 = 73.33%. Market 2025: 650 / 1000 = 65%.
    assert value(con, view, "market_loss_ratio", 2025, "Total") == pytest.approx(0.65)
    assert value(con, view, "market_gap_pts", 2025, "Total") == pytest.approx(
        (1100 / 1500 - 0.65) * 100
    )
    assert value(con, view, "market_gap_pts", 2023, "Total") == pytest.approx(-2.0)  # 68% - 70%
    assert value(con, view, "market_gap_pts", 2025, "Total", HDI) == pytest.approx(
        (880 / 1200 - 0.65) * 100
    )
    assert value(con, view, "market_status", 2025, "Total") == "ok"
    # The market file has no 2024.
    assert value(con, view, "market_gap_pts", 2024, "Total") is None
    assert value(con, view, "market_status", 2024, "Total") == "no market data"
    # V1 compares totals only.
    assert con.execute(f"SELECT DISTINCT line_group FROM {view}").fetchall() == [("Total",)]


# Rules the ratios share


def test_ratio_is_null_when_the_base_is_zero_or_negative(tmp_path):
    lines = {
        "C0070": {"R0110": 100, "R0140": 10, "R0210": 100, "R0300": 90, "R0310": 50, "R0400": 45},
        "C0080": {"R0110": 0, "R0140": 5, "R0210": 0, "R0300": -5, "R0310": 20, "R0400": 20},
    }
    con = build(tmp_path, {AGCS: {2025: lines}})
    try:
        for view, column in (
            ("kpi_gross_loss_ratio", "gross_loss_ratio"),
            ("kpi_ceded_share", "ceded_share"),
            ("kpi_net_loss_ratio", "net_loss_ratio"),
            ("kpi_net_expense_ratio", "net_expense_ratio"),
        ):
            assert value(con, view, column, 2025, "Liability") is None, view
        assert value(con, "kpi_gross_loss_ratio", "gross_loss_ratio", 2025, "Property") == 0.5
    finally:
        con.close()


def test_amount_is_null_when_no_row_is_reported_and_missing_rows_are_not_zero(tmp_path):
    # Liability reports written premium only: GEP and claims have no rows at all.
    lines = {
        "C0070": {"R0110": 100, "R0210": 100, "R0310": 50},
        "C0080": {"R0110": 40},
    }
    con = build(tmp_path, {AGCS: {2025: lines}})
    try:
        assert value(con, "kpi_gwp", "gwp_teur", 2025, "Liability") == 40
        assert value(con, "kpi_gep", "gep_teur", 2025, "Liability") is None
        assert value(con, "kpi_gross_claims", "gross_claims_teur", 2025, "Liability") is None
        assert value(con, "kpi_gross_loss_ratio", "gross_loss_ratio", 2025, "Liability") is None
    finally:
        con.close()


def test_growth_does_not_bridge_a_missing_year(tmp_path):
    # Liability exists in 2023 and 2025 but not in 2024: 2025 has no prior year.
    year = {"C0070": {"R0110": 100, "R0210": 100, "R0310": 50}}
    with_liability = year | {"C0080": {"R0110": 40, "R0210": 40, "R0310": 20}}
    con = build(tmp_path, {AGCS: {2023: with_liability, 2024: year, 2025: with_liability}})
    try:
        assert value(con, "kpi_gwp_growth", "gwp_growth", 2025, "Liability") is None
        assert (
            value(con, "kpi_loss_ratio_change", "loss_ratio_change_pts", 2025, "Liability") is None
        )
        assert value(con, "kpi_loss_ratio_3y_avg", "loss_ratio_3y_avg", 2025, "Liability") is None
        assert value(con, "kpi_gwp_growth", "gwp_growth", 2025, "Property") == pytest.approx(0.0)
    finally:
        con.close()
