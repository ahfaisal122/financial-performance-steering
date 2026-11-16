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

EIOPA_FILE_NAME = "SA_Premiums_Claims_Expenses.csv"
EIOPA_HEADER = [
    "Reporting country",
    "Reference period",
    "Item",
    "Business type",
    "Item code",
    "Value",
    "Date of extraction (yyyymmdd)",
    "Number of submissions (per reporting country, reference date and undertaking type)",
]
# One EIOPA test row: (country, period, business type, item code, value).
EiopaRow = tuple[str, str, str, str, object]


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


def market_rows(
    country: str,
    year: int,
    earned: tuple[object, object, object] = (600, 300, 100),
    claims: tuple[object, object, object] = (400, 200, 50),
) -> list[EiopaRow]:
    """Non-life gross earned premium and gross claims of one country and year."""
    period = f"Y{year}"
    codes = ("R0210", "R0220", "R0230", "R0310", "R0320", "R0330")
    return [
        (country, period, "Non-Life", code, value)
        for code, value in zip(codes, earned + claims, strict=True)
    ]


def write_eiopa_file(
    paths: Paths,
    rows: list[EiopaRow],
    header: list[str] | None = None,
    name: str = EIOPA_FILE_NAME,
) -> Path:
    """Write an EIOPA statistics file with the layout of the real download."""
    paths.eiopa_dir.mkdir(parents=True, exist_ok=True)
    path = paths.eiopa_dir / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header or EIOPA_HEADER)
        for country, period, business_type, item_code, value in rows:
            writer.writerow(
                [country, period, "item", business_type, item_code, value, "20260723", 5]
            )
    return path


def new_project(root: Path) -> Paths:
    """An empty project: the real line groups and insurers, no reference values, and a
    small EIOPA file with Germany, another country and a life row."""
    paths = Paths(root=root)
    paths.sfcr_dir.mkdir(parents=True)
    paths.reference_dir.mkdir(parents=True)
    for name in ("lob_groups.csv", "insurers.csv"):
        shutil.copy(REPO_ROOT / "data" / "reference" / name, paths.reference_dir)
    write_reference_values(paths, [])
    write_eiopa_file(
        paths,
        market_rows("GERMANY", 2025)
        + market_rows("FRANCE", 2025, earned=(1, 1, 1), claims=(9, 9, 9))
        + [("GERMANY", "Y2025", "Life", "R1410", 777)],
    )
    return paths


@pytest.fixture
def project(tmp_path: Path) -> Paths:
    """An empty project in a temp folder, see new_project."""
    return new_project(tmp_path)


@pytest.fixture
def real_project(tmp_path: Path) -> Paths:
    """The real raw and reference files, with the warehouse in a temp folder."""
    shutil.copytree(REPO_ROOT / "data" / "raw" / "sfcr", tmp_path / "data" / "raw" / "sfcr")
    shutil.copytree(REPO_ROOT / "data" / "raw" / "eiopa", tmp_path / "data" / "raw" / "eiopa")
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
