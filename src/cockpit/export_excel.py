"""Excel export of the marts with the KPI columns as live formulas (FR-1.22).

Run after the pipeline: python -m cockpit.export_excel

The amounts are values from the warehouse. Every KPI column is an Excel formula
on those amounts, written to follow the same rules as the SQL views: a ratio is
empty when its base is zero, negative or missing, and the prior year is exactly
the year before.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import duckdb
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from cockpit.config import Paths

EXPORT_FILE = "cockpit_marts.xlsx"

# The KPI columns, in the order they follow the mart columns on a sheet.
KPI_COLUMNS = (
    "gross_loss_ratio",
    "ceded_share",
    "net_loss_ratio",
    "net_expense_ratio",
    "gwp_growth",
    "loss_ratio_change_pts",
    "mix_share",
)

AMOUNT_FORMAT = "#,##0"
RATIO_FORMAT = "0.0%"
POINTS_FORMAT = "0.0"


@dataclass(frozen=True)
class Sheet:
    title: str
    table: str
    line_column: str  # the column that names the line within an insurer and year
    order_by: str
    with_mix_share: bool


SHEETS: tuple[Sheet, ...] = (
    Sheet(
        title="line_group_year",
        table="mart_line_group_year",
        line_column="line_group",
        order_by="insurer, year, is_total, line_group",
        with_mix_share=True,
    ),
    Sheet(
        title="lob_year",
        table="mart_lob_year",
        line_column="lob_code",
        order_by="insurer, year, lob_code",
        with_mix_share=False,
    ),
)


def _ratio(numerator: str, base: str) -> str:
    """numerator / base, empty unless both are numbers and the base is above zero."""
    return f'=IF(AND(ISNUMBER({numerator}),ISNUMBER({base}),{base}>0),{numerator}/{base},"")'


def _kpi_formulas(sheet: Sheet, col: dict[str, str], row: int, last_row: int) -> dict[str, str]:
    """The KPI formulas of one data row, keyed by KPI column name."""

    def cell(name: str) -> str:
        return f"{col[name]}{row}"

    def whole(name: str) -> str:
        return f"${col[name]}$2:${col[name]}${last_row}"

    # The same insurer and line, one year earlier.
    prior_row = (
        f"{whole('insurer')},{cell('insurer')},{whole('year')},{cell('year')}-1,"
        f"{whole(sheet.line_column)},{cell(sheet.line_column)}"
    )
    gwp_prior = f"SUMIFS({whole('gwp_teur')},{prior_row})"
    # The prior year's loss ratio is read from the loss ratio column itself. A numeric
    # criterion skips empty and text cells, so it counts only rows that have a loss ratio.
    loss_ratio_prior = f"SUMIFS({whole('gross_loss_ratio')},{prior_row})"
    prior_has_loss_ratio = f'COUNTIFS({prior_row},{whole("gross_loss_ratio")},">-1E+300")>0'

    formulas = {
        "gross_loss_ratio": _ratio(cell("gross_claims_teur"), cell("gep_teur")),
        "ceded_share": _ratio(cell("ceded_written_teur"), cell("gwp_teur")),
        "net_loss_ratio": _ratio(cell("net_claims_teur"), cell("net_earned_teur")),
        "net_expense_ratio": _ratio(cell("expenses_teur"), cell("net_earned_teur")),
        "gwp_growth": (
            f"=IF(AND(ISNUMBER({cell('gwp_teur')}),{gwp_prior}>0),"
            f'{cell("gwp_teur")}/{gwp_prior}-1,"")'
        ),
        "loss_ratio_change_pts": (
            f"=IF(AND(ISNUMBER({cell('gross_loss_ratio')}),{prior_has_loss_ratio}),"
            f'({cell("gross_loss_ratio")}-{loss_ratio_prior})*100,"")'
        ),
    }
    if sheet.with_mix_share:
        # Share of the line group in the earned premium of all line groups, as in kpi_mix_share.
        gep_all_lines = (
            f"SUMIFS({whole('gep_teur')},{whole('insurer')},{cell('insurer')},"
            f'{whole("year")},{cell("year")},{whole(sheet.line_column)},"<>Total")'
        )
        formulas["mix_share"] = (
            f'=IF(OR({cell(sheet.line_column)}="Total",NOT(ISNUMBER({cell("gep_teur")})),'
            f'{gep_all_lines}<=0),"",{cell("gep_teur")}/{gep_all_lines})'
        )
    return formulas


def _write_sheet(ws: Worksheet, con: duckdb.DuckDBPyConnection, sheet: Sheet) -> None:
    result = con.execute(f"SELECT * FROM {sheet.table} ORDER BY {sheet.order_by}")
    names = [description[0] for description in result.description]
    rows = result.fetchall()
    last_row = len(rows) + 1
    kpi_names = [name for name in KPI_COLUMNS if name != "mix_share" or sheet.with_mix_share]
    col = {name: get_column_letter(i) for i, name in enumerate(names + kpi_names, start=1)}

    ws.append(names + kpi_names)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"

    for row_number, values in enumerate(rows, start=2):
        ws.append([float(v) if isinstance(v, Decimal) else v for v in values])
        formulas = _kpi_formulas(sheet, col, row_number, last_row)
        for offset, name in enumerate(kpi_names, start=len(names) + 1):
            cell = ws.cell(row=row_number, column=offset, value=formulas[name])
            cell.number_format = POINTS_FORMAT if name.endswith("_pts") else RATIO_FORMAT
        for name in names:
            if name.endswith("_teur"):
                ws[f"{col[name]}{row_number}"].number_format = AMOUNT_FORMAT

    for index in range(1, len(names) + len(kpi_names) + 1):
        ws.column_dimensions[get_column_letter(index)].width = 18


def _write_definitions(ws: Worksheet, con: duckdb.DuckDBPyConnection) -> None:
    result = con.execute(
        "SELECT kpi_name, formula, unit, scope, caveat FROM kpi_definitions ORDER BY sort_order"
    )
    ws.append([description[0] for description in result.description])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for values in result.fetchall():
        ws.append(list(values))
    ws.append([])
    ws.append(["Amounts are in EUR thousand, as reported in the SFCR template S.05.01.02."])
    ws.append(["Figures follow German local GAAP (HGB), not IFRS 17."])
    ws.append(["Ratios are fractions shown as percent; changes are in percentage points."])
    for letter, width in zip("ABCDE", (32, 44, 10, 44, 60), strict=True):
        ws.column_dimensions[letter].width = width


def export(paths: Paths | None = None) -> Path:
    """Write the workbook from the warehouse and return its path."""
    paths = paths or Paths()
    if not paths.warehouse.is_file():
        raise FileNotFoundError(
            f"{paths.warehouse} does not exist. Run the pipeline first: python -m cockpit.pipeline"
        )
    workbook = Workbook()
    workbook.remove(workbook.active)
    con = duckdb.connect(str(paths.warehouse), read_only=True)
    try:
        for sheet in SHEETS:
            _write_sheet(workbook.create_sheet(sheet.title), con, sheet)
        _write_definitions(workbook.create_sheet("kpi_definitions"), con)
    finally:
        con.close()

    paths.exports_dir.mkdir(parents=True, exist_ok=True)
    target = paths.exports_dir / EXPORT_FILE
    workbook.save(target)
    return target


def main() -> int:
    try:
        target = export()
    except FileNotFoundError as error:
        print(f"STOPPED: {error}")
        return 1
    print(f"excel    {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
