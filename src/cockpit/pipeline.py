"""Run the pipeline from raw files: python -m cockpit.pipeline

Order: ingest, then the quality gate. Later steps build only after the gate passes.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

from cockpit.config import Paths
from cockpit.db import connect
from cockpit.ingest import IngestError, IngestResult, load_reference, load_sfcr
from cockpit.quality import CheckResult, QualityGateError, enforce_gate, run_checks


@dataclass(frozen=True)
class PipelineResult:
    ingest: IngestResult
    checks: list[CheckResult]


def run(paths: Paths | None = None) -> PipelineResult:
    """Run every step. Raises IngestError or QualityGateError when the run must stop."""
    paths = paths or Paths()
    con = connect(paths.warehouse)
    try:
        ingest = load_sfcr(con, paths)
        print(
            f"ingest   raw_s050102: {ingest.rows_in_table} rows from {ingest.files_found} files "
            f"({ingest.files_loaded} loaded, {ingest.files_skipped} unchanged, "
            f"{ingest.files_removed} removed)"
        )
        load_reference(con, paths)

        checks = run_checks(con, paths)
        for result in checks:
            state = "FAIL" if result.failures else "WARN" if result.warnings else "ok"
            print(
                f"quality  {result.check.requirement} {result.check.table}: {state} "
                f"({result.rows} rows, {result.failures} fail, {result.warnings} warn)"
            )
        enforce_gate(checks)
        return PipelineResult(ingest, checks)
    finally:
        con.close()


def main() -> int:
    started = time.perf_counter()
    try:
        run()
    except (IngestError, QualityGateError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 1
    print(f"done in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
