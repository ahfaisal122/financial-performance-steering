"""DuckDB connection and SQL file runner."""

from __future__ import annotations

from pathlib import Path

import duckdb


def connect(warehouse: Path) -> duckdb.DuckDBPyConnection:
    """Open the warehouse file, creating its folder on first use."""
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(warehouse))


def run_sql_file(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    """Run one model file. Each file builds exactly one table."""
    con.execute(path.read_text(encoding="utf-8"))
