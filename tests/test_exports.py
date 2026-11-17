"""Excel export (FR-1.22) and the generated KPI definitions page (NFR-10)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from openpyxl import load_workbook

from cockpit import export_excel, kpi_docs, pipeline
from cockpit.config import REPO_ROOT

KPI_COLUMNS = (
    "gross_loss_ratio",
    "ceded_share",
    "net_loss_ratio",
    "net_expense_ratio",
    "gwp_growth",
    "loss_ratio_change_pts",
)


@pytest.fixture
def built(real_project):
    pipeline.run(real_project)
    return real_project


def header_of(ws) -> list[str]:
    return [cell.value for cell in ws[1]]


def test_workbook_has_both_marts_and_the_kpi_definitions(built):
    workbook = load_workbook(export_excel.export(built))

    assert workbook.sheetnames == ["line_group_year", "lob_year", "kpi_definitions"]
    assert workbook["kpi_definitions"].cell(row=2, column=1).value == "Gross written premium (GWP)"


@pytest.mark.parametrize(
    ("sheet", "table", "kpi_columns"),
    [
        ("line_group_year", "mart_line_group_year", KPI_COLUMNS + ("mix_share",)),
        ("lob_year", "mart_lob_year", KPI_COLUMNS),
    ],
)
def test_kpi_columns_are_formulas_not_pasted_values(
    built, open_warehouse, sheet, table, kpi_columns
):
    ws = load_workbook(export_excel.export(built))[sheet]
    header = header_of(ws)
    (mart_rows,) = open_warehouse(built).execute(f"SELECT COUNT(*) FROM {table}").fetchone()

    assert ws.max_row == mart_rows + 1
    assert tuple(header[-len(kpi_columns) :]) == kpi_columns
    for name in kpi_columns:
        column = header.index(name) + 1
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=column)
            assert cell.data_type == "f", f"{sheet} {name} row {row}"
            assert cell.value.startswith("=IF(")


def test_amounts_are_the_mart_values(built, open_warehouse):
    ws = load_workbook(export_excel.export(built))["line_group_year"]
    header = header_of(ws)
    mart = (
        open_warehouse(built)
        .execute(
            "SELECT insurer, year, line_group, gwp_teur, gep_teur, gross_claims_teur "
            "FROM mart_line_group_year ORDER BY insurer, year, is_total, line_group"
        )
        .fetchall()
    )

    columns = [header.index(name) + 1 for name in ("insurer", "year", "line_group")]
    amounts = [header.index(name) + 1 for name in ("gwp_teur", "gep_teur", "gross_claims_teur")]
    for row_number, expected in enumerate(mart, start=2):
        key = tuple(ws.cell(row=row_number, column=c).value for c in columns)
        values = tuple(ws.cell(row=row_number, column=c).value for c in amounts)
        assert key == expected[:3]
        assert values == tuple(None if v is None else float(v) for v in expected[3:])

    # AGCS 2024 total GWP, as printed in the SFCR.
    total = next(
        row
        for row in ws.iter_rows(min_row=2, values_only=True)
        if row[:3] == ("AGCS SE", 2024, "Total")
    )
    assert Decimal(str(total[header.index("gwp_teur")])) == Decimal("6523288")


def test_loss_ratio_formula_points_at_claims_and_earned_premium_of_its_own_row(built):
    ws = load_workbook(export_excel.export(built))["line_group_year"]
    header = header_of(ws)
    letter = {name: ws.cell(row=1, column=i + 1).column_letter for i, name in enumerate(header)}
    claims, gep = letter["gross_claims_teur"], letter["gep_teur"]

    formula = ws.cell(row=5, column=header.index("gross_loss_ratio") + 1).value

    assert formula == f'=IF(AND(ISNUMBER({claims}5),ISNUMBER({gep}5),{gep}5>0),{claims}5/{gep}5,"")'


def test_export_without_a_warehouse_says_to_run_the_pipeline(project):
    with pytest.raises(FileNotFoundError, match="Run the pipeline first"):
        export_excel.export(project)


def test_committed_kpi_definitions_page_matches_the_table(built):
    """docs/kpi_definitions.md is generated; regenerate it with `make docs` when this fails."""
    generated = kpi_docs.write(built).read_text(encoding="utf-8")
    committed = (REPO_ROOT / "docs" / "kpi_definitions.md").read_text(encoding="utf-8")

    assert generated == committed


def test_kpi_definitions_page_lists_every_kpi_and_line_group(built):
    page = kpi_docs.write(built).read_text(encoding="utf-8")

    assert page.count("\n| ") >= 13 + 6
    assert "| Market gap | LR(company) - LR(German market), in points |" in page
    assert "| Property | C0070, C0160 |" in page
