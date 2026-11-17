"""Data model FR-1.8 to FR-1.10, the KPI glossary of FR-1.11, and the model checks."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cockpit import pipeline
from cockpit.config import REPO_ROOT
from cockpit.models import MODEL_FOLDERS, ModelError
from conftest import balanced_rows, write_eiopa_file, write_sfcr_file

MART_FIGURES = (
    "gwp_teur",
    "gep_teur",
    "gross_claims_teur",
    "ceded_written_teur",
    "ceded_earned_teur",
    "ceded_claims_teur",
    "net_written_teur",
    "net_earned_teur",
    "net_claims_teur",
    "expenses_teur",
)


@pytest.fixture
def real(real_project, open_warehouse):
    pipeline.run(real_project)
    return open_warehouse(real_project)


def test_every_sql_file_is_in_the_build_order():
    for folder, models in MODEL_FOLDERS:
        files = {path.stem for path in (REPO_ROOT / "sql" / folder).glob("*.sql")}
        assert files == set(models), folder
        assert len(models) == len(set(models)), folder


# FR-1.8 dimensions


def test_dimensions_hold_what_the_raw_data_holds(real):
    assert real.execute("SELECT insurer, insurer_short, role FROM dim_insurer").fetchall() == [
        ("AGCS SE", "AGCS", "focus"),
        ("HDI Global SE", "HDI", "peer"),
    ]
    assert real.execute("SELECT year FROM dim_year ORDER BY year").fetchall() == [
        (2022,),
        (2023,),
        (2024,),
        (2025,),
    ]
    assert real.execute("SELECT COUNT(*), COUNT(DISTINCT lob_code) FROM dim_lob").fetchone() == (
        16,
        16,
    )
    assert real.execute("SELECT COUNT(*), COUNT(DISTINCT row_code) FROM dim_metric").fetchone() == (
        20,
        20,
    )


def test_dim_lob_carries_names_line_group_and_business_type(real):
    rows = real.execute(
        "SELECT lob_code, lob_name_de, lob_name_en, line_group, business_type, is_total "
        "FROM dim_lob WHERE lob_code IN ('C0070', 'C0160', 'C0200') ORDER BY lob_code"
    ).fetchall()
    assert rows == [
        (
            "C0070",
            "Feuer- und andere Sachversicherungen",
            "Fire and other damage to property",
            "Property",
            "direct_prop",
            False,
        ),
        ("C0160", "Sache", "Property", "Property", "nonprop_re", False),
        ("C0200", "Gesamt", "Total", "Total", "total", True),
    ]


def test_dim_metric_carries_name_block_and_measure(real):
    rows = real.execute(
        "SELECT row_code, metric_name, block, measure FROM dim_metric "
        "WHERE row_code IN ('R0130', 'R0300', 'R0410', 'R0550') ORDER BY row_code"
    ).fetchall()
    assert rows == [
        ("R0130", "written_gross_nonprop_re", "Premiums written", "gwp"),
        ("R0300", "earned_net", "Premiums earned", "net_earned"),
        ("R0410", "other_tp_change_gross_direct", "Changes in other technical provisions", None),
        ("R0550", "expenses_incurred", "Expenses incurred", "expenses"),
    ]


def test_every_fact_row_joins_to_every_dimension(real):
    (joined,) = real.execute(
        """
        SELECT COUNT(*)
        FROM fct_s050102 AS fct
        INNER JOIN dim_insurer USING (insurer)
        INNER JOIN dim_lob USING (lob_code)
        INNER JOIN dim_metric USING (row_code)
        INNER JOIN dim_year USING (year)
        """
    ).fetchone()
    assert joined == 1186


# FR-1.9 fact table


def test_fact_table_has_the_same_rows_and_total_value_as_raw(real):
    raw = real.execute("SELECT COUNT(*), SUM(value_teur) FROM raw_s050102").fetchone()
    fct = real.execute("SELECT COUNT(*), SUM(value_teur) FROM fct_s050102").fetchone()
    assert fct == raw == (1186, Decimal("548282506"))


def test_fact_rows_keep_their_source_file(real):
    row = real.execute(
        "SELECT value_teur, template, source_file FROM fct_s050102 "
        "WHERE insurer = 'AGCS SE' AND year = 2025 AND lob_code = 'C0070' AND row_code = 'R0110'"
    ).fetchone()
    assert row == (Decimal("1327995"), "S.05.01.02", "data/raw/sfcr/agcs_2025_s050102.csv")


# FR-1.10 marts


def test_mart_lob_year_has_one_row_per_insurer_year_and_line(real):
    rows, keys, totals = real.execute(
        "SELECT COUNT(*), COUNT(DISTINCT (insurer, year, lob_code)), "
        "COUNT(*) FILTER (WHERE lob_code = 'C0200') FROM mart_lob_year"
    ).fetchone()
    assert rows == keys
    assert totals == 0


def test_mart_lob_year_totals_match_the_total_column(real):
    """Each figure, summed over the lines, is within 3 TEUR of the C0200 column."""
    sums = ", ".join(f"SUM({figure}) AS {figure}" for figure in MART_FIGURES)
    gaps = ", ".join(f"MAX(ABS(lines.{f} - total.{f}))" for f in MART_FIGURES)
    row = real.execute(
        f"""
        WITH lines AS (SELECT insurer, year, {sums} FROM mart_lob_year GROUP BY insurer, year)
        SELECT COUNT(*), {gaps}
        FROM lines
        INNER JOIN mart_line_group_year AS total
            ON lines.insurer = total.insurer AND lines.year = total.year AND total.is_total
        """
    ).fetchone()
    assert row[0] == 8
    assert all(gap <= 3 for gap in row[1:]), row


def test_total_row_equals_the_reported_total_column(real):
    row = real.execute(
        "SELECT gwp_teur FROM mart_line_group_year "
        "WHERE insurer = 'AGCS SE' AND year = 2024 AND is_total"
    ).fetchone()
    assert row == (Decimal("6523288"),)


def test_mart_line_group_year_has_one_total_row_per_insurer_and_year(real):
    rows = real.execute(
        "SELECT COUNT(*), COUNT(DISTINCT (insurer, year)) FROM mart_line_group_year WHERE is_total"
    ).fetchone()
    assert rows == (8, 8)


# FR-1.11 KPI glossary


def test_kpi_definitions_lists_the_13_kpis_of_section_4(real):
    assert real.execute("SELECT kpi_id FROM kpi_definitions ORDER BY sort_order").fetchall() == [
        ("gwp",),
        ("gep",),
        ("gross_claims",),
        ("gross_loss_ratio",),
        ("ceded_share",),
        ("net_loss_ratio",),
        ("net_expense_ratio",),
        ("gwp_growth",),
        ("loss_ratio_change",),
        ("loss_ratio_3y_avg",),
        ("mix_share",),
        ("peer_gap",),
        ("market_gap",),
    ]


def test_every_kpi_definition_points_at_a_real_view_column(real):
    definitions = real.execute(
        "SELECT kpi_id, view_name, value_column FROM kpi_definitions"
    ).fetchall()
    assert len(definitions) == 13

    for _kpi_id, view_name, value_column in definitions:
        (found,) = real.execute(
            "SELECT COUNT(*) FROM information_schema.columns c "
            "INNER JOIN information_schema.tables t USING (table_name) "
            "WHERE t.table_type = 'VIEW' AND c.table_name = ? AND c.column_name = ?",
            [view_name, value_column],
        ).fetchone()
        assert found == 1, f"{view_name}.{value_column}"


# FR-1.2 and FR-1.15: the German market total


def test_market_mart_has_the_german_non_life_total_for_2016_to_2025(real):
    years = [
        year
        for (year,) in real.execute("SELECT year FROM mart_market_year ORDER BY year").fetchall()
    ]
    assert years == list(range(2016, 2026))
    # 2025 by hand from the file: 123498.821642 + 78703.352719 + 18343.472092.
    assert real.execute(
        "SELECT market, gwp_meur FROM mart_market_year WHERE year = 2025"
    ).fetchone() == ("German market", Decimal("220545.646453"))
    # EIOPA delivers no claims for 2016.
    assert real.execute(
        "SELECT gross_claims_meur FROM mart_market_year WHERE year = 2016"
    ).fetchone() == (None,)


def test_real_market_gap_exists_for_both_companies_and_all_four_years(real):
    rows = real.execute(
        "SELECT insurer, COUNT(*), COUNT(market_gap_pts) FROM kpi_market_gap "
        "WHERE market_status = 'ok' GROUP BY insurer ORDER BY insurer"
    ).fetchall()
    assert rows == [("AGCS SE", 4, 4), ("HDI Global SE", 4, 4)]


def test_staging_keeps_non_life_rows_only(project, open_warehouse):
    write_sfcr_file(project, "Test SE", 2025, balanced_rows())

    pipeline.run(project)

    con = open_warehouse(project)
    assert con.execute("SELECT COUNT(*) FROM raw_eiopa").fetchone() == (7,)
    assert con.execute("SELECT DISTINCT country, year FROM stg_eiopa_nonlife").fetchall() == [
        ("GERMANY", 2025)
    ]
    assert con.execute("SELECT COUNT(*) FROM stg_eiopa_nonlife").fetchone() == (6,)
    assert con.execute("SELECT gep_meur, gross_claims_meur FROM mart_market_year").fetchall() == [
        (Decimal("1000"), Decimal("650"))
    ]


def test_market_file_without_non_life_rows_stops_the_pipeline(project):
    write_sfcr_file(project, "Test SE", 2025, balanced_rows())
    write_eiopa_file(project, [("GERMANY", "Y2025", "Life", "R1410", 777)])

    with pytest.raises(ModelError, match="Non-Life"):
        pipeline.run(project)


# Model checks


def test_column_code_without_a_line_group_stops_the_pipeline(project):
    rows = balanced_rows() + [("C0999", "R0110", 0)]
    write_sfcr_file(project, "Test SE", 2025, rows)

    with pytest.raises(ModelError, match="C0999"):
        pipeline.run(project)


def test_insurer_outside_the_reference_file_gets_role_other(project, open_warehouse):
    write_sfcr_file(project, "Test SE", 2025, balanced_rows())

    pipeline.run(project)

    con = open_warehouse(project)
    assert con.execute("SELECT * FROM dim_insurer").fetchall() == [("Test SE", "Test SE", "other")]
    assert con.execute("SELECT COUNT(*) FROM kpi_peer_gap").fetchone() == (0,)


def test_real_peer_gap_has_no_peer_data_for_financial_lines_only(real):
    rows = real.execute(
        "SELECT line_group, peer_status, COUNT(*) FROM kpi_peer_gap "
        "WHERE peer_status <> 'ok' GROUP BY line_group, peer_status"
    ).fetchall()
    assert rows == [("Financial lines", "no peer data", 4)]
