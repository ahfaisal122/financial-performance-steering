"""Shared fixtures: the real project, and small hand-made projects in a temp folder."""

from __future__ import annotations

import csv
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import duckdb
import pytest

from cockpit.config import REPO_ROOT, Paths
from cockpit.db import connect
from cockpit.ingest import RAW_COLUMNS

# One test row: (lob_code, row_code, value). The value is written as given, so "-" stays a dash.
Row = tuple[str, str, object]

MAIN_LINE_CODES = ("C0060", "C0070", "C0080", "C0120")


def balanced_rows() -> list[Row]:
    """Four main lines that add up to the total, with gross minus ceded equal to net."""
    rows: list[Row] = []
    for lob_code in MAIN_LINE_CODES:
        rows += [(lob_code, "R0110", 100), (lob_code, "R0140", 40), (lob_code, "R0200", 60)]
    rows += [("C0200", "R0110", 400), ("C0200", "R0140", 160), ("C0200", "R0200", 240)]
    return rows


def replace_value(rows: list[Row], lob_code: str, row_code: str, value: object) -> list[Row]:
    return [
        (lob, row, value if (lob, row) == (lob_code, row_code) else old) for lob, row, old in rows
    ]


def write_sfcr_file(paths: Paths, insurer: str, year: int, rows: list[Row]) -> Path:
    """Write one company-year file in the raw file schema."""
    paths.sfcr_dir.mkdir(parents=True, exist_ok=True)
    path = paths.sfcr_dir / f"{insurer.lower().replace(' ', '_')}_{year}_s050102.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(RAW_COLUMNS)
        for lob_code, row_code, value in rows:
            business_type = "total" if lob_code == "C0200" else "direct_prop"
            writer.writerow(
                [insurer, year, "S.05.01.02", lob_code, "name de", "name en", business_type]
                + [row_code, "metric", value]
            )
    return path


def write_reference_values(paths: Paths, rows: list[tuple[str, int, str, object]]) -> None:
    path = paths.reference_dir / "dq_reference_values.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["insurer", "year", "metric", "value_teur", "source"])
        for insurer, year, metric, value in rows:
            writer.writerow([insurer, year, metric, value, "test"])


@pytest.fixture
def project(tmp_path: Path) -> Paths:
    """An empty project in a temp folder: the real line groups, no reference values yet."""
    paths = Paths(root=tmp_path)
    paths.sfcr_dir.mkdir(parents=True)
    paths.reference_dir.mkdir(parents=True)
    shutil.copy(REPO_ROOT / "data" / "reference" / "lob_groups.csv", paths.reference_dir)
    write_reference_values(paths, [])
    return paths


@pytest.fixture
def real_project(tmp_path: Path) -> Paths:
    """The real raw and reference files, with the warehouse in a temp folder."""
    shutil.copytree(REPO_ROOT / "data" / "raw" / "sfcr", tmp_path / "data" / "raw" / "sfcr")
    shutil.copytree(REPO_ROOT / "data" / "reference", tmp_path / "data" / "reference")
    return Paths(root=tmp_path)


@pytest.fixture
def open_warehouse() -> Iterator[Callable[[Paths], duckdb.DuckDBPyConnection]]:
    """Open a project's warehouse; every connection is closed after the test."""
    connections: list[duckdb.DuckDBPyConnection] = []

    def _open(paths: Paths) -> duckdb.DuckDBPyConnection:
        con = connect(paths.warehouse)
        connections.append(con)
        return con

    yield _open
    for con in connections:
        con.close()
