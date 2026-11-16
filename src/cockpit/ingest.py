"""Load the raw SFCR files and the reference files into DuckDB (FR-1.1, FR-1.3)."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cockpit.config import Paths
from cockpit.db import run_sql_file

# Column order and types of the raw file schema (requirements section 3).
RAW_COLUMNS: dict[str, str] = {
    "insurer": "VARCHAR",
    "year": "INTEGER",
    "template": "VARCHAR",
    "lob_code": "VARCHAR",
    "lob_name_de": "VARCHAR",
    "lob_name_en": "VARCHAR",
    "business_type": "VARCHAR",
    "row_code": "VARCHAR",
    "metric": "VARCHAR",
    "value_teur": "DECIMAL(18, 3)",
}

REFERENCE_FILES = ("lob_groups.csv", "dq_reference_values.csv")

_COLUMN_SPEC = ", ".join(f"'{name}': '{dtype}'" for name, dtype in RAW_COLUMNS.items())

# A dash means "no value" in the reports: stored as NULL, never as zero.
_INSERT_SQL = f"""
INSERT INTO raw_s050102
SELECT {", ".join(RAW_COLUMNS)}, ? AS source_file, ?::TIMESTAMP AS loaded_at
FROM read_csv(
    ?,
    header = true,
    auto_detect = false,
    delim = ',',
    quote = '"',
    columns = {{{_COLUMN_SPEC}}},
    nullstr = ['', '-', '–', '—']
)
"""


class IngestError(Exception):
    """A raw or reference file is missing or does not match the expected layout."""


@dataclass(frozen=True)
class IngestResult:
    files_found: int
    files_loaded: int
    files_skipped: int
    files_removed: int
    rows_in_files: int
    rows_in_table: int


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_file_rows(path: Path) -> int:
    """Check the header and count the data rows without DuckDB, as an independent count."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != list(RAW_COLUMNS):
            raise IngestError(
                f"{path.name}: header does not match the raw file schema.\n"
                f"  expected: {','.join(RAW_COLUMNS)}\n"
                f"  found:    {','.join(header or [])}"
            )
        return sum(1 for row in reader if row)


def _load_file(
    con: duckdb.DuckDBPyConnection, path: Path, source_file: str, sha256: str, file_rows: int
) -> None:
    """Replace the rows of one source file, all or nothing."""
    loaded_at = datetime.now(UTC).replace(tzinfo=None)
    con.begin()
    try:
        con.execute("DELETE FROM raw_s050102 WHERE source_file = ?", [source_file])
        con.execute(_INSERT_SQL, [source_file, loaded_at, str(path)])
        (loaded_rows,) = con.execute(
            "SELECT COUNT(*) FROM raw_s050102 WHERE source_file = ?", [source_file]
        ).fetchone()
        if loaded_rows != file_rows:
            raise IngestError(
                f"{path.name}: the file has {file_rows} rows but {loaded_rows} were loaded."
            )
        con.execute(
            "INSERT OR REPLACE INTO raw_load_log VALUES (?, ?, ?, ?)",
            [source_file, sha256, file_rows, loaded_at],
        )
        con.commit()
    except duckdb.Error as error:
        con.rollback()
        raise IngestError(f"{path.name}: could not be loaded. {error}") from error
    except IngestError:
        con.rollback()
        raise


def load_sfcr(con: duckdb.DuckDBPyConnection, paths: Paths) -> IngestResult:
    """Load every SFCR file into raw_s050102. Unchanged files are left as they are."""
    run_sql_file(con, paths.sql_dir / "10_raw" / "raw_s050102.sql")
    run_sql_file(con, paths.sql_dir / "10_raw" / "raw_load_log.sql")

    files = sorted(paths.sfcr_dir.glob("*.csv"))
    if not files:
        raise IngestError(f"No SFCR files found in {paths.sfcr_dir}.")

    sources = {path.relative_to(paths.root).as_posix(): path for path in files}
    already_loaded = dict(con.execute("SELECT source_file, sha256 FROM raw_load_log").fetchall())

    removed = [source for source in already_loaded if source not in sources]
    for source in removed:
        con.execute("DELETE FROM raw_s050102 WHERE source_file = ?", [source])
        con.execute("DELETE FROM raw_load_log WHERE source_file = ?", [source])

    loaded = 0
    rows_in_files = 0
    for source, path in sources.items():
        file_rows = _count_file_rows(path)
        rows_in_files += file_rows
        sha256 = _sha256(path)
        if already_loaded.get(source) == sha256:
            continue
        _load_file(con, path, source, sha256, file_rows)
        loaded += 1

    (rows_in_table,) = con.execute("SELECT COUNT(*) FROM raw_s050102").fetchone()
    if rows_in_table != rows_in_files:
        raise IngestError(
            f"raw_s050102 has {rows_in_table} rows but the files hold {rows_in_files}."
        )

    return IngestResult(
        files_found=len(files),
        files_loaded=loaded,
        files_skipped=len(files) - loaded,
        files_removed=len(removed),
        rows_in_files=rows_in_files,
        rows_in_table=rows_in_table,
    )


def load_reference(con: duckdb.DuckDBPyConnection, paths: Paths) -> None:
    """Rebuild the reference tables from data/reference."""
    for name in REFERENCE_FILES:
        if not (paths.reference_dir / name).is_file():
            raise IngestError(f"Reference file missing: {paths.reference_dir / name}")

    con.execute("SET VARIABLE reference_dir = ?", [str(paths.reference_dir)])
    try:
        run_sql_file(con, paths.sql_dir / "10_raw" / "ref_lob_groups.sql")
        run_sql_file(con, paths.sql_dir / "10_raw" / "ref_dq_reference_values.sql")
    except duckdb.Error as error:
        raise IngestError(f"A reference file could not be loaded. {error}") from error
