"""Load the raw SFCR files, the EIOPA file and the reference files (FR-1.1 to FR-1.3)."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cockpit.config import EIOPA_COUNTRY, EIOPA_DOWNLOAD_HINT, Paths
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

REFERENCE_FILES = ("lob_groups.csv", "insurers.csv", "dq_reference_values.csv")

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
    already_loaded = _logged_files(con, paths.sfcr_dir, paths)

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


# raw_eiopa column -> (header in the EIOPA file, True when only its start has to match).
EIOPA_COLUMNS: dict[str, tuple[str, bool]] = {
    "reporting_country": ("Reporting country", False),
    "reference_period": ("Reference period", False),
    "item": ("Item", False),
    "business_type": ("Business type", False),
    "item_code": ("Item code", False),
    "value": ("Value", False),
    "extraction_date": ("Date of extraction", True),
    "submissions": ("Number of submissions", True),
}


@dataclass(frozen=True)
class EiopaResult:
    source_file: str
    rows_in_table: int
    loaded: bool


def _logged_files(con: duckdb.DuckDBPyConnection, folder: Path, paths: Paths) -> dict[str, str]:
    """Fingerprints of the files already loaded from one raw folder."""
    prefix = folder.relative_to(paths.root).as_posix() + "/"
    return dict(
        con.execute(
            "SELECT source_file, sha256 FROM raw_load_log WHERE starts_with(source_file, ?)",
            [prefix],
        ).fetchall()
    )


def _detect_eiopa_columns(path: Path, header: list[str]) -> dict[str, str]:
    """Find each column the pipeline needs in the file header; stop if one is missing."""
    found: dict[str, str] = {}
    missing: list[str] = []
    for column, (label, start_only) in EIOPA_COLUMNS.items():
        wanted = label.lower()
        matches = [
            name
            for name in header
            if (
                name.strip().lower().startswith(wanted)
                if start_only
                else name.strip().lower() == wanted
            )
        ]
        if len(matches) == 1:
            found[column] = matches[0]
        else:
            missing.append(label)
    if missing:
        raise IngestError(
            f"{path.name}: column not found: {', '.join(missing)}.\n"
            f"  columns in the file: {' | '.join(header)}"
        )
    return found


def _scan_eiopa_file(path: Path) -> tuple[dict[str, str], int]:
    """Detect the columns and count the rows of the country, without DuckDB."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None) or []
        columns = _detect_eiopa_columns(path, header)
        country_index = header.index(columns["reporting_country"])
        countries = [row[country_index].strip() for row in reader if row]
    country_rows = sum(1 for country in countries if country.upper() == EIOPA_COUNTRY)
    if country_rows == 0:
        raise IngestError(
            f"{path.name}: no rows for reporting country {EIOPA_COUNTRY}.\n"
            f"  countries in the file: {', '.join(sorted(set(countries)))}"
        )
    return columns, country_rows


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _load_eiopa_file(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    source_file: str,
    sha256: str,
    columns: dict[str, str],
    file_rows: int,
) -> None:
    """Replace the EIOPA rows with the country rows of this file, all or nothing."""
    col = {column: _quoted(name) for column, name in columns.items()}
    insert_sql = f"""
        INSERT INTO raw_eiopa
        SELECT
            {col["reporting_country"]}, {col["reference_period"]}, {col["item"]},
            {col["business_type"]}, {col["item_code"]}, CAST({col["value"]} AS DOUBLE),
            {col["extraction_date"]}, CAST({col["submissions"]} AS INTEGER),
            ? AS source_file, ?::TIMESTAMP AS loaded_at
        FROM read_csv(?, header = true, all_varchar = true, delim = ',', quote = '"', nullstr = '')
        WHERE upper(trim({col["reporting_country"]})) = ?
    """
    loaded_at = datetime.now(UTC).replace(tzinfo=None)
    con.begin()
    try:
        con.execute("DELETE FROM raw_eiopa")
        con.execute(insert_sql, [source_file, loaded_at, str(path), EIOPA_COUNTRY])
        (loaded_rows,) = con.execute("SELECT COUNT(*) FROM raw_eiopa").fetchone()
        if loaded_rows != file_rows:
            raise IngestError(
                f"{path.name}: the file has {file_rows} rows for {EIOPA_COUNTRY} "
                f"but {loaded_rows} were loaded."
            )
        bad_periods = con.execute(
            "SELECT DISTINCT COALESCE(reference_period, '(empty)') FROM raw_eiopa "
            "WHERE reference_period IS NULL "
            "OR NOT regexp_full_match(reference_period, 'Y[0-9]{4}') "
            "ORDER BY 1"
        ).fetchall()
        if bad_periods:
            raise IngestError(
                f"{path.name}: reference period is not a year like Y2025: "
                + ", ".join(period for (period,) in bad_periods)
            )
        duplicates = con.execute(
            "SELECT reference_period, business_type, item_code FROM raw_eiopa "
            "GROUP BY ALL HAVING COUNT(*) > 1 ORDER BY ALL LIMIT 5"
        ).fetchall()
        if duplicates:
            raise IngestError(
                f"{path.name}: more than one row for the same year, business type and item code, "
                f"for example {duplicates[0]}."
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


def load_eiopa(con: duckdb.DuckDBPyConnection, paths: Paths) -> EiopaResult:
    """Load the country rows of the EIOPA file into raw_eiopa. An unchanged file is left as is."""
    run_sql_file(con, paths.sql_dir / "10_raw" / "raw_eiopa.sql")
    run_sql_file(con, paths.sql_dir / "10_raw" / "raw_load_log.sql")

    files = sorted(paths.eiopa_dir.glob("*.csv"))
    if len(files) != 1:
        raise IngestError(
            f"Expected exactly one EIOPA csv file in {paths.eiopa_dir}, found {len(files)}.\n"
            f"  {EIOPA_DOWNLOAD_HINT}"
        )
    path = files[0]
    source = path.relative_to(paths.root).as_posix()

    already_loaded = _logged_files(con, paths.eiopa_dir, paths)
    for stale in already_loaded:
        if stale != source:
            con.execute("DELETE FROM raw_eiopa WHERE source_file = ?", [stale])
            con.execute("DELETE FROM raw_load_log WHERE source_file = ?", [stale])

    columns, file_rows = _scan_eiopa_file(path)
    sha256 = _sha256(path)
    needs_load = already_loaded.get(source) != sha256
    if needs_load:
        _load_eiopa_file(con, path, source, sha256, columns, file_rows)

    (rows_in_table,) = con.execute("SELECT COUNT(*) FROM raw_eiopa").fetchone()
    return EiopaResult(source_file=source, rows_in_table=rows_in_table, loaded=needs_load)


def load_reference(con: duckdb.DuckDBPyConnection, paths: Paths) -> None:
    """Rebuild the reference tables from data/reference."""
    for name in REFERENCE_FILES:
        if not (paths.reference_dir / name).is_file():
            raise IngestError(f"Reference file missing: {paths.reference_dir / name}")

    con.execute("SET VARIABLE reference_dir = ?", [str(paths.reference_dir)])
    try:
        run_sql_file(con, paths.sql_dir / "10_raw" / "ref_lob_groups.sql")
        run_sql_file(con, paths.sql_dir / "10_raw" / "ref_insurers.sql")
        run_sql_file(con, paths.sql_dir / "10_raw" / "ref_dq_reference_values.sql")
    except duckdb.Error as error:
        raise IngestError(f"A reference file could not be loaded. {error}") from error
