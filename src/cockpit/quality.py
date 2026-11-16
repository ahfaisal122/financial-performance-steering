"""Data quality checks and the quality gate (FR-1.4 to FR-1.7).

Each check is one SQL file in sql/15_quality that builds one dq_ table with a
`status` column. A row with status 'fail' stops the pipeline; 'warn' is reported
and the run goes on.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from cockpit.config import (
    RECONCILIATION_TOLERANCE_TEUR,
    REFERENCE_TOLERANCE_TEUR,
    Paths,
)
from cockpit.db import run_sql_file


@dataclass(frozen=True)
class Check:
    requirement: str
    table: str
    description: str


CHECKS: tuple[Check, ...] = (
    Check("FR-1.4", "dq_reconciliation", "lines add up to the total column"),
    Check("FR-1.5", "dq_reference_check", "GWP totals match the printed reference values"),
    Check("FR-1.6", "dq_net_check", "gross minus reinsurers' share equals net"),
    Check("FR-1.7", "dq_completeness", "every year and main line is present"),
)


@dataclass(frozen=True)
class CheckResult:
    check: Check
    rows: int
    failures: int
    warnings: int


class QualityGateError(Exception):
    """At least one check has failing rows. Nothing downstream may build."""


def run_checks(con: duckdb.DuckDBPyConnection, paths: Paths) -> list[CheckResult]:
    """Build every dq_ table and count its failing and warning rows."""
    con.execute(f"SET VARIABLE dq_tolerance_teur = {RECONCILIATION_TOLERANCE_TEUR}")
    con.execute(f"SET VARIABLE dq_reference_tolerance_teur = {REFERENCE_TOLERANCE_TEUR}")

    results = []
    for check in CHECKS:
        run_sql_file(con, paths.sql_dir / "15_quality" / f"{check.table}.sql")
        rows, failures, warnings = con.execute(
            f"""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE status = 'fail'),
                COUNT(*) FILTER (WHERE status = 'warn')
            FROM {check.table}
            """
        ).fetchone()
        results.append(CheckResult(check, rows, failures, warnings))
    return results


def enforce_gate(results: list[CheckResult]) -> None:
    """Raise if any check failed, naming the table that holds the failing rows."""
    failed = [result for result in results if result.failures]
    if not failed:
        return
    lines = [
        f"  {result.check.requirement} {result.check.description}: "
        f"{result.failures} failing rows, see {result.check.table} where status = 'fail'"
        for result in failed
    ]
    raise QualityGateError("Quality gate failed.\n" + "\n".join(lines))
