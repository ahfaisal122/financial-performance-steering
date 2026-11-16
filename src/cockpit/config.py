"""Project paths and data quality tolerances."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# FR-1.4 and FR-1.6: lines against total, and gross minus ceded against net.
RECONCILIATION_TOLERANCE_TEUR = 3
# FR-1.5 and success criterion S2: figures reconcile within EUR 1k.
REFERENCE_TOLERANCE_TEUR = 1


@dataclass(frozen=True)
class Paths:
    """Where the pipeline reads and writes. Tests point `root` at a temp folder."""

    root: Path = REPO_ROOT
    sql_dir: Path = REPO_ROOT / "sql"

    @property
    def sfcr_dir(self) -> Path:
        return self.root / "data" / "raw" / "sfcr"

    @property
    def reference_dir(self) -> Path:
        return self.root / "data" / "reference"

    @property
    def warehouse(self) -> Path:
        return self.root / "warehouse" / "cockpit.duckdb"
