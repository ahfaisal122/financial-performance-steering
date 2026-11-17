"""The Streamlit dashboard (FR-1.17 to FR-1.20), run headless.

Acceptance for all pages: slicers for insurer, year and line group; the HGB footer
note; every number equals its SQL view.
"""

from __future__ import annotations

import duckdb
import pytest
from streamlit.testing.v1 import AppTest

from cockpit import pipeline
from cockpit.config import REPO_ROOT

APP_DIR = REPO_ROOT / "app"
APP_FILE = str(APP_DIR / "cockpit_app.py")
HGB = "Figures follow German local GAAP (HGB)"

PAGES = {
    "page_overview": "Overview",
    "page_line_of_business": "Line of business",
    "page_peer_market": "Peer and market",
    "page_data_quality": "Data quality and definitions",
}
# The focus company on the latest year, the peer on a line it does not write in the
# first year, and a small line in the first year (no prior year, no 3-year average).
SLICES = [
    ("AGCS SE", "AGCS", 2025, None),
    ("HDI Global SE", "HDI", 2022, "Financial lines"),
    ("AGCS SE", "AGCS", 2022, "Motor"),
]


@pytest.fixture
def cockpit(real_project, monkeypatch):
    """The real data built in a temp folder, with the app pointed at it.

    Yields a read-only connection, like the app's own: DuckDB does not allow one
    process to open the same file both read-only and read-write.
    """
    pipeline.run(real_project)
    monkeypatch.setenv("COCKPIT_ROOT", str(real_project.root))
    con = duckdb.connect(str(real_project.warehouse), read_only=True)
    yield con
    con.close()


def run_app() -> AppTest:
    at = AppTest.from_file(APP_FILE, default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def page_script(app_dir, module_name, insurer, insurer_short, year, line_group):
    """Render one page with fixed slicers, the way the app does."""
    import importlib
    import sys

    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import ui

    importlib.import_module(module_name).render(
        ui.Slicers(insurer=insurer, insurer_short=insurer_short, year=year, line_group=line_group)
    )
    ui.footer()


def run_page(module_name: str, insurer: str, short: str, year: int, line_group) -> AppTest:
    at = AppTest.from_function(
        page_script,
        kwargs={
            "app_dir": str(APP_DIR),
            "module_name": module_name,
            "insurer": insurer,
            "insurer_short": short,
            "year": year,
            "line_group": line_group,
        },
        default_timeout=60,
    ).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def metrics(at: AppTest) -> dict[str, tuple[str, str]]:
    return {metric.label: (metric.value, metric.delta) for metric in at.metric}


# Every page


@pytest.mark.parametrize("module_name", PAGES)
@pytest.mark.parametrize(("insurer", "short", "year", "line_group"), SLICES)
def test_every_page_renders_with_its_title_and_the_hgb_footer(
    cockpit, module_name, insurer, short, year, line_group
):
    at = run_page(module_name, insurer, short, year, line_group)

    assert [title.value for title in at.title] == [PAGES[module_name]]
    assert any(HGB in caption.value for caption in at.caption)


def test_slicers_for_insurer_year_and_line_group_default_to_the_focus_company(cockpit):
    at = run_app()

    assert {box.label: box.value for box in at.selectbox} == {
        "Insurer": "AGCS SE",
        "Year": 2025,
        "Line group": "All line groups",
    }
    assert at.selectbox(key="slicer_line_group").options == [
        "All line groups",
        "Property",
        "Liability",
        "Marine, aviation and transport",
        "Financial lines",
        "Motor",
        "Other",
    ]
    assert any(HGB in caption.value for caption in at.caption)


def test_app_without_a_warehouse_says_to_build_it(project, monkeypatch):
    monkeypatch.setenv("COCKPIT_ROOT", str(project.root))

    at = AppTest.from_file(APP_FILE, default_timeout=60).run()

    assert not at.exception
    assert "warehouse does not exist" in at.error[0].value


# Overview


def test_overview_cards_equal_the_sql_views(cockpit):
    gwp, growth, loss_ratio, change, ceded = cockpit.execute(
        """
        SELECT gwp.gwp_teur, growth.gwp_growth, lr.gross_loss_ratio,
            lr.loss_ratio_change_pts, ceded.ceded_share
        FROM kpi_gwp AS gwp
        JOIN kpi_gwp_growth AS growth USING (insurer, year, line_group)
        JOIN kpi_loss_ratio_change AS lr USING (insurer, year, line_group)
        JOIN kpi_ceded_share AS ceded USING (insurer, year, line_group)
        WHERE gwp.insurer = 'AGCS SE' AND gwp.year = 2025 AND gwp.line_group = 'Total'
        """
    ).fetchone()

    cards = metrics(run_app())

    assert cards["Gross written premium, EUR m"][0] == f"{float(gwp) / 1000:,.1f}" == "6,581.3"
    assert cards["GWP growth"][0] == f"{growth:+.1%}"
    assert cards["Gross loss ratio"] == (f"{loss_ratio:.1%}", f"{change:+.1f} pts against 2024")
    assert cards["Ceded share"][0] == f"{ceded:.1%}"


def test_overview_follows_the_slicers(cockpit):
    at = run_app()
    at.selectbox(key="slicer_insurer").set_value("HDI Global SE")
    at.selectbox(key="slicer_year").set_value(2024)
    at.selectbox(key="slicer_line_group").set_value("Property")
    at.run()
    assert not at.exception

    (gwp, loss_ratio) = cockpit.execute(
        "SELECT g.gwp_teur, l.gross_loss_ratio FROM kpi_gwp g "
        "JOIN kpi_gross_loss_ratio l USING (insurer, year, line_group) "
        "WHERE g.insurer = 'HDI Global SE' AND g.year = 2024 AND g.line_group = 'Property'"
    ).fetchone()
    cards = metrics(at)
    assert cards["Gross written premium, EUR m"][0] == f"{float(gwp) / 1000:,.1f}"
    assert cards["Gross loss ratio"][0] == f"{loss_ratio:.1%}"


def test_overview_top_3_movers_are_the_largest_loss_ratio_changes(cockpit):
    expected = cockpit.execute(
        "SELECT line_group, gross_loss_ratio, loss_ratio_change_pts, gross_loss_ratio_prior "
        "FROM analysis_yoy WHERE insurer = 'AGCS SE' AND year = 2025 AND NOT is_total "
        "ORDER BY ABS(loss_ratio_change_pts) DESC LIMIT 3"
    ).fetchall()

    cards = metrics(run_app())

    for line_group, ratio, change, prior in expected:
        assert cards[line_group] == (f"{ratio:.1%}", f"{change:+.1f} pts from {prior:.1%}")
    assert len(cards) == 4 + 3


def test_overview_walk_text_matches_the_walk_view(cockpit):
    prior, current, rate, mix, total = cockpit.execute(
        "SELECT gross_loss_ratio_prior, gross_loss_ratio, rate_effect_pts, mix_effect_pts, "
        "total_effect_pts FROM analysis_lr_walk "
        "WHERE insurer = 'AGCS SE' AND year = 2025 AND is_total"
    ).fetchone()

    text = " ".join(block.value for block in run_app().markdown)

    assert f"from **{prior:.1%}** to **{current:.1%}** ({total:+.2f} pts)" in text
    assert f"**{rate:+.2f} pts** because line groups' own loss ratios moved" in text
    assert f"**{mix:+.2f} pts** because the book shifted" in text


def test_overview_first_year_says_there_is_no_prior_year(cockpit):
    at = run_page("page_overview", "AGCS SE", "AGCS", 2022, None)

    messages = [info.value for info in at.info]
    assert any("No walk for 2022" in message for message in messages)
    assert any("No movers for 2022" in message for message in messages)


def test_overview_line_without_figures_says_so_instead_of_showing_zero(cockpit):
    at = run_page("page_overview", "HDI Global SE", "HDI", 2022, "Financial lines")

    assert "reports no figures for Financial lines in 2022" in at.info[0].value
    assert "Gross written premium, EUR m" not in metrics(at)


# Line of business


def test_line_of_business_table_equals_the_views(cockpit):
    expected = cockpit.execute(
        """
        SELECT a.line_group, g.gwp_teur, a.gross_loss_ratio, a.loss_ratio_3y_avg, m.mix_share
        FROM analysis_rolling_avg a
        JOIN kpi_gwp g USING (insurer, year, line_group)
        JOIN kpi_mix_share m USING (insurer, year, line_group)
        WHERE a.insurer = 'AGCS SE' AND a.year = 2025 AND NOT a.is_total
        """
    ).fetchall()

    table = run_page("page_line_of_business", "AGCS SE", "AGCS", 2025, None).dataframe[0].value

    shown = table.set_index("Line group")
    assert len(shown) == len(expected) == 6
    for line_group, gwp, ratio, average, share in expected:
        row = shown.loc[line_group]
        assert row["GWP, EUR m"] == f"{float(gwp) / 1000:,.1f}"
        assert row["Gross loss ratio"] == f"{ratio:.1%}"
        assert row["3-year average"] == f"{average:.1%}"
        assert row["Mix share"] == f"{share:.1%}"


def test_line_of_business_shows_na_before_the_3_year_average_exists(cockpit):
    table = (
        run_page("page_line_of_business", "AGCS SE", "AGCS", 2023, "Property").dataframe[0].value
    )

    assert table["Line group"].tolist() == ["Property"]
    assert table["3-year average"].tolist() == ["n/a"]


# Peer and market


def test_peer_page_table_equals_the_view_and_says_no_peer_data(cockpit):
    expected = cockpit.execute(
        "SELECT line_group, focus_loss_ratio, peer_loss_ratio, peer_gap_pts, peer_status "
        "FROM analysis_peer_market WHERE year = 2025"
    ).fetchall()

    table = run_page("page_peer_market", "AGCS SE", "AGCS", 2025, None).dataframe[0].value

    shown = table.set_index("Line group")
    assert len(shown) == len(expected) == 7
    for line_group, focus, peer, gap, status in expected:
        row = shown.loc[line_group]
        assert row["AGCS"] == f"{focus:.1%}"
        if status == "ok":
            assert (row["HDI"], row["Peer gap"]) == (f"{peer:.1%}", f"{gap:+.1f} pts")
        else:
            assert (row["HDI"], row["Peer gap"]) == ("no peer data", "no peer data")
    assert shown.loc["Financial lines", "Peer gap"] == "no peer data"


def test_peer_page_market_tiles_equal_the_view(cockpit):
    market, focus_gap, peer_gap = cockpit.execute(
        "SELECT market_loss_ratio, focus_market_gap_pts, peer_market_gap_pts "
        "FROM analysis_peer_market WHERE year = 2025 AND is_total"
    ).fetchone()

    tiles = metrics(run_page("page_peer_market", "AGCS SE", "AGCS", 2025, None))

    assert tiles["German market, gross loss ratio"][0] == f"{market:.1%}"
    assert tiles["AGCS against the market"][0] == f"{focus_gap:+.1f} pts"
    assert tiles["HDI against the market"][0] == f"{peer_gap:+.1f} pts"


# Data quality and definitions


def test_data_quality_page_shows_reconciliation_and_the_glossary(cockpit):
    at = run_page("page_data_quality", "AGCS SE", "AGCS", 2024, None)
    tables = [frame.value for frame in at.dataframe]

    reconciliation = tables[0]
    (rows,) = cockpit.execute(
        "SELECT COUNT(*) FROM dq_reconciliation WHERE insurer = 'AGCS SE' AND year = 2024"
    ).fetchone()
    assert len(reconciliation) == rows
    assert set(reconciliation["Status"]) == {"ok", "total_only"}

    glossary = next(table for table in tables if "Formula" in table.columns)
    assert len(glossary) == 13
    assert glossary["KPI"].iloc[0] == "Gross written premium (GWP)"

    reference = next(table for table in tables if "Printed, TEUR" in table.columns)
    assert reference["Pipeline, TEUR"].tolist() == [6523288]
    assert any(HGB in info.value for info in at.info)
