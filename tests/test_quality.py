"""Data quality checks FR-1.4 to FR-1.7 and the quality gate."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cockpit import pipeline
from cockpit.quality import QualityGateError
from conftest import (
    balanced_rows,
    replace_value,
    write_reference_values,
    write_sfcr_file,
)


def run_stopped(paths) -> str:
    """Run the pipeline, expect the gate to stop it, and return the message."""
    with pytest.raises(QualityGateError) as stopped:
        pipeline.run(paths)
    return str(stopped.value)


# FR-1.4 reconciliation: lines against the total column


def test_reconciliation_passes_within_3_teur(project, open_warehouse):
    rows = replace_value(balanced_rows(), "C0200", "R0110", 403)
    write_sfcr_file(project, "Test SE", 2025, rows)

    pipeline.run(project)

    row = (
        open_warehouse(project)
        .execute(
            "SELECT sum_lines_teur, total_teur, gap_teur, status FROM dq_reconciliation "
            "WHERE row_code = 'R0110'"
        )
        .fetchone()
    )
    assert row == (Decimal("400"), Decimal("403"), Decimal("-3"), "ok")


def test_reconciliation_gap_above_3_teur_stops_the_pipeline(project, open_warehouse):
    rows = replace_value(balanced_rows(), "C0200", "R0110", 404)
    write_sfcr_file(project, "Test SE", 2025, rows)

    message = run_stopped(project)

    assert "FR-1.4" in message and "dq_reconciliation" in message
    failing = (
        open_warehouse(project)
        .execute("SELECT row_code, gap_teur FROM dq_reconciliation WHERE status = 'fail'")
        .fetchall()
    )
    assert failing == [("R0110", Decimal("-4"))]


def test_reconciliation_fails_when_the_total_is_missing(project):
    rows = [row for row in balanced_rows() if row[:2] != ("C0200", "R0110")]
    write_sfcr_file(project, "Test SE", 2025, rows)

    assert "FR-1.4" in run_stopped(project)


def test_total_only_row_r1300_does_not_fail(project, open_warehouse):
    rows = balanced_rows() + [("C0200", "R1300", 500)]
    write_sfcr_file(project, "Test SE", 2025, rows)

    pipeline.run(project)

    row = (
        open_warehouse(project)
        .execute("SELECT gap_teur, status FROM dq_reconciliation WHERE row_code = 'R1300'")
        .fetchone()
    )
    assert row == (None, "total_only")


# FR-1.5 reference values: GWP against printed figures


def test_reference_value_matches(project, open_warehouse):
    write_sfcr_file(project, "Test SE", 2025, balanced_rows())
    write_reference_values(project, [("Test SE", 2025, "gwp", 400)])

    pipeline.run(project)

    row = (
        open_warehouse(project)
        .execute(
            "SELECT reference_value_teur, pipeline_value_teur, gap_teur, status "
            "FROM dq_reference_check"
        )
        .fetchone()
    )
    assert row == (Decimal("400"), Decimal("400"), Decimal("0"), "ok")


def test_reference_value_off_by_2_teur_stops_the_pipeline(project):
    write_sfcr_file(project, "Test SE", 2025, balanced_rows())
    write_reference_values(project, [("Test SE", 2025, "gwp", 402)])

    message = run_stopped(project)

    assert "FR-1.5" in message and "dq_reference_check" in message


def test_reference_value_without_data_stops_the_pipeline(project):
    write_sfcr_file(project, "Test SE", 2025, balanced_rows())
    write_reference_values(project, [("Test SE", 2024, "gwp", 400)])

    assert "FR-1.5" in run_stopped(project)


def test_agcs_2024_gwp_equals_6523288(real_project, open_warehouse):
    pipeline.run(real_project)

    row = (
        open_warehouse(real_project)
        .execute(
            "SELECT pipeline_value_teur, status FROM dq_reference_check "
            "WHERE insurer = 'AGCS SE' AND year = 2024 AND metric = 'gwp'"
        )
        .fetchone()
    )
    assert row == (Decimal("6523288"), "ok")


# FR-1.6 net check: gross minus reinsurers' share equals net


def test_net_gap_above_3_teur_warns_and_does_not_stop(project, open_warehouse):
    # Property net is 4 TEUR too high; the total moves with it so the lines still add up.
    rows = replace_value(balanced_rows(), "C0070", "R0200", 64)
    rows = replace_value(rows, "C0200", "R0200", 244)
    write_sfcr_file(project, "Test SE", 2025, rows)

    result = pipeline.run(project)

    net_check = next(r for r in result.checks if r.check.table == "dq_net_check")
    assert (net_check.failures, net_check.warnings) == (0, 2)
    warned = (
        open_warehouse(project)
        .execute(
            "SELECT lob_code, block, gross_teur, ceded_teur, net_teur, gap_teur "
            "FROM dq_net_check WHERE status = 'warn' ORDER BY lob_code"
        )
        .fetchall()
    )
    assert warned == [
        ("C0070", "written", Decimal("100"), Decimal("40"), Decimal("64"), Decimal("-4")),
        ("C0200", "written", Decimal("400"), Decimal("160"), Decimal("244"), Decimal("-4")),
    ]


def test_net_gap_of_3_teur_is_ok(project, open_warehouse):
    rows = replace_value(balanced_rows(), "C0070", "R0200", 63)
    rows = replace_value(rows, "C0200", "R0200", 243)
    write_sfcr_file(project, "Test SE", 2025, rows)

    pipeline.run(project)

    statuses = (
        open_warehouse(project).execute("SELECT DISTINCT status FROM dq_net_check").fetchall()
    )
    assert statuses == [("ok",)]


# FR-1.7 completeness: years per insurer, main lines per year


def test_missing_year_is_listed_and_stops_the_pipeline(project, open_warehouse):
    for year in (2022, 2023, 2024, 2025):
        write_sfcr_file(project, "Full SE", year, balanced_rows())
    for year in (2022, 2023, 2025):
        write_sfcr_file(project, "Gap SE", year, balanced_rows())

    message = run_stopped(project)

    assert "FR-1.7" in message and "dq_completeness" in message
    missing = open_warehouse(project).execute("SELECT * FROM dq_completeness").fetchall()
    assert missing == [("missing_year", "Gap SE", 2024, None, "fail")]


def test_missing_main_line_is_listed_as_a_warning(project, open_warehouse):
    without_financial_lines = [row for row in balanced_rows() if row[0] != "C0120"]
    rows = replace_value(without_financial_lines, "C0200", "R0110", 300)
    rows = replace_value(rows, "C0200", "R0140", 120)
    rows = replace_value(rows, "C0200", "R0200", 180)
    write_sfcr_file(project, "Test SE", 2025, rows)

    pipeline.run(project)

    missing = open_warehouse(project).execute("SELECT * FROM dq_completeness").fetchall()
    assert missing == [("missing_main_line", "Test SE", 2025, "Financial lines", "warn")]


def test_main_line_with_only_null_values_counts_as_missing(project, open_warehouse):
    rows = [(lob, row, "-" if lob == "C0120" else value) for lob, row, value in balanced_rows()]
    rows = replace_value(rows, "C0200", "R0110", 300)
    rows = replace_value(rows, "C0200", "R0140", 120)
    rows = replace_value(rows, "C0200", "R0200", 180)
    write_sfcr_file(project, "Test SE", 2025, rows)

    pipeline.run(project)

    missing = (
        open_warehouse(project)
        .execute("SELECT check_type, line_group FROM dq_completeness")
        .fetchall()
    )
    assert missing == [("missing_main_line", "Financial lines")]


# The gate on the real files


def test_real_files_pass_the_quality_gate(real_project, open_warehouse):
    result = pipeline.run(real_project)

    assert [r.failures for r in result.checks] == [0, 0, 0, 0]
    con = open_warehouse(real_project)
    assert con.execute(
        "SELECT status, COUNT(*) FROM dq_reconciliation GROUP BY status ORDER BY status"
    ).fetchall() == [("ok", 125), ("total_only", 7)]
    assert con.execute("SELECT COUNT(*) FROM dq_net_check WHERE status <> 'ok'").fetchone() == (0,)
    assert con.execute(
        "SELECT insurer, year, line_group FROM dq_completeness ORDER BY year"
    ).fetchall() == [
        ("HDI Global SE", 2022, "Financial lines"),
        ("HDI Global SE", 2023, "Financial lines"),
        ("HDI Global SE", 2024, "Financial lines"),
    ]
