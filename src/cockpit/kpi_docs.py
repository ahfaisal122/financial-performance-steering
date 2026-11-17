"""Write docs/kpi_definitions.md from the kpi_definitions table (NFR-10).

Run after the pipeline: python -m cockpit.kpi_docs

The page is generated, so it cannot drift from the table the dashboard tooltips
read. A test fails when the committed page differs from the table.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from cockpit.config import Paths

DOC_FILE = "kpi_definitions.md"

INTRO = """# KPI definitions

Generated from the table `kpi_definitions` by `python -m cockpit.kpi_docs`. Do not edit by hand:
change `sql/30_marts/kpi_definitions.sql`, run the pipeline, then run the command again.

Every KPI is computed from the Solvency II template S.05.01.02 (premiums, claims and expenses
by line of business). The row codes in the formulas (R0110, R0120 and so on) are the rows of
that template.
"""

RULES = """## Rules that apply to every KPI

- **Accounting basis.** The SFCR figures follow German local GAAP (HGB). They differ from the
  IFRS 17 figures the groups publish.
- **Units.** Amounts are in EUR thousand, as reported. A unit of `ratio` is a fraction
  (0.65 means 65%). A unit of `points` is percentage points (5 means +5 points).
- **Levels.** Every KPI exists per line group and for the company total. The total is the
  total column (C0200) as reported.
- **Empty values.** A ratio is empty when its base is zero, negative or missing. An amount is
  empty when the report shows no value for any of its rows; it is never set to zero.
- **Prior year.** The prior year is exactly the year before. A gap in the years is not bridged.
- **Cross-company comparison.** Compare companies on gross figures only. The net loss ratio and
  the net expense ratio are valid within one company only.
- **Market gap.** Total level only: company total against the German non-life market total
  from EIOPA. There is no market gap per line in version 1.
"""


def _cell(value: object) -> str:
    return "" if value is None else str(value).replace("|", "\\|")


def render(con: duckdb.DuckDBPyConnection) -> str:
    """The whole page as markdown."""
    kpis = con.execute(
        "SELECT kpi_name, formula, unit, scope, caveat, view_name, value_column "
        "FROM kpi_definitions ORDER BY sort_order"
    ).fetchall()
    line_groups = con.execute(
        "SELECT line_group, string_agg(lob_code, ', ' ORDER BY lob_code) "
        "FROM ref_lob_groups WHERE line_group <> 'Total' GROUP BY line_group ORDER BY line_group"
    ).fetchall()

    lines = [INTRO, "## KPIs", ""]
    lines += ["| KPI | Formula | Unit | Scope | Caveat | View and column |"]
    lines += ["| --- | --- | --- | --- | --- | --- |"]
    for name, formula, unit, scope, caveat, view_name, value_column in kpis:
        where = f"`{view_name}.{value_column}`" if view_name else ""
        cells = [_cell(name), _cell(formula), _cell(unit), _cell(scope), _cell(caveat), where]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Line groups", ""]
    lines += ["| Line group | Column codes of S.05.01.02 |", "| --- | --- |"]
    lines += [f"| {_cell(group)} | {codes} |" for group, codes in line_groups]
    lines += ["", RULES]
    return "\n".join(lines)


def write(paths: Paths | None = None) -> Path:
    paths = paths or Paths()
    if not paths.warehouse.is_file():
        raise FileNotFoundError(
            f"{paths.warehouse} does not exist. Run the pipeline first: python -m cockpit.pipeline"
        )
    con = duckdb.connect(str(paths.warehouse), read_only=True)
    try:
        page = render(con)
    finally:
        con.close()
    target = paths.docs_dir / DOC_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    return target


def main() -> int:
    try:
        target = write()
    except FileNotFoundError as error:
        print(f"STOPPED: {error}")
        return 1
    print(f"docs     {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
