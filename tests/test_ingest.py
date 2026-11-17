"""Ingestion: FR-1.1 (SFCR load), FR-1.2 (EIOPA load), FR-1.3 (idempotent runs), data rules."""

from __future__ import annotations

import csv
from decimal import Decimal

import pytest

from cockpit import pipeline
from cockpit.ingest import IngestError, load_eiopa, load_reference, load_sfcr
from conftest import (
    EIOPA_HEADER,
    GDV_SOURCE,
    balanced_rows,
    market_rows,
    replace_value,
    write_eiopa_file,
    write_gdv_file,
    write_sfcr_file,
)


def snapshot(con) -> dict[str, list[tuple]]:
    """Every table and view, fully sorted, so two runs can be compared row by row."""
    names = [
        name
        for (name,) in con.execute(
            "SELECT table_name FROM information_schema.tables ORDER BY table_name"
        ).fetchall()
    ]
    return {name: con.execute(f"SELECT * FROM {name} ORDER BY ALL").fetchall() for name in names}


def test_real_files_load_1186_rows(real_project, open_warehouse):
    result = load_sfcr(open_warehouse(real_project), real_project)

    assert result.files_found == 8
    assert result.rows_in_files == 1186
    assert result.rows_in_table == 1186


def test_real_values_are_loaded_unchanged(real_project, open_warehouse):
    con = open_warehouse(real_project)
    load_sfcr(con, real_project)

    for path in sorted(real_project.sfcr_dir.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            file_values = sorted(Decimal(row["value_teur"]) for row in csv.DictReader(handle))
        source_file = f"data/raw/sfcr/{path.name}"
        loaded_values = [
            value
            for (value,) in con.execute(
                "SELECT value_teur FROM raw_s050102 WHERE source_file = ? ORDER BY 1",
                [source_file],
            ).fetchall()
        ]
        assert loaded_values == file_values, path.name


def test_every_row_keeps_its_lineage(real_project, open_warehouse):
    con = open_warehouse(real_project)
    load_sfcr(con, real_project)

    (rows_without_lineage,) = con.execute(
        """
        SELECT COUNT(*) FROM raw_s050102
        WHERE insurer IS NULL OR year IS NULL OR template IS NULL OR lob_code IS NULL
            OR row_code IS NULL OR source_file IS NULL OR loaded_at IS NULL
        """
    ).fetchone()
    assert rows_without_lineage == 0


def test_dash_and_empty_are_null_and_negatives_are_kept(project, open_warehouse):
    rows = balanced_rows() + [
        ("C0010", "R0110", "-"),
        ("C0020", "R0110", ""),
        ("C0030", "R0110", -25),
    ]
    write_sfcr_file(project, "Test SE", 2025, rows)
    con = open_warehouse(project)
    load_sfcr(con, project)

    loaded = dict(
        con.execute(
            "SELECT lob_code, value_teur FROM raw_s050102 "
            "WHERE lob_code IN ('C0010', 'C0020', 'C0030')"
        ).fetchall()
    )
    assert loaded == {"C0010": None, "C0020": None, "C0030": Decimal("-25")}


def test_two_runs_give_identical_tables(real_project, open_warehouse):
    pipeline.run(real_project)
    first = snapshot(open_warehouse(real_project))
    open_warehouse(real_project).close()

    pipeline.run(real_project)
    second = snapshot(open_warehouse(real_project))

    assert first == second


def test_changed_file_is_reloaded_without_duplicates(project, open_warehouse):
    write_sfcr_file(project, "Test SE", 2025, balanced_rows())
    con = open_warehouse(project)
    load_sfcr(con, project)

    changed = replace_value(balanced_rows(), "C0070", "R0110", 101)
    write_sfcr_file(project, "Test SE", 2025, changed)
    result = load_sfcr(con, project)

    assert result.files_loaded == 1
    assert result.rows_in_table == len(balanced_rows())
    (value,) = con.execute(
        "SELECT value_teur FROM raw_s050102 WHERE lob_code = 'C0070' AND row_code = 'R0110'"
    ).fetchone()
    assert value == Decimal("101")


def test_rows_of_a_removed_file_are_removed(project, open_warehouse):
    write_sfcr_file(project, "Test SE", 2024, balanced_rows())
    removed_file = write_sfcr_file(project, "Test SE", 2025, balanced_rows())
    con = open_warehouse(project)
    load_sfcr(con, project)

    removed_file.unlink()
    result = load_sfcr(con, project)

    assert result.files_removed == 1
    assert con.execute("SELECT DISTINCT year FROM raw_s050102").fetchall() == [(2024,)]


def test_wrong_header_stops_with_the_file_name(project, open_warehouse):
    path = write_sfcr_file(project, "Test SE", 2025, balanced_rows())
    path.write_text(path.read_text().replace("value_teur", "value_eur", 1))

    with pytest.raises(IngestError, match="test_se_2025_s050102.csv: header"):
        load_sfcr(open_warehouse(project), project)


def test_text_in_the_value_column_stops_and_loads_nothing(project, open_warehouse):
    rows = replace_value(balanced_rows(), "C0070", "R0110", "n/a")
    write_sfcr_file(project, "Test SE", 2025, rows)
    con = open_warehouse(project)

    with pytest.raises(IngestError, match="test_se_2025_s050102.csv: could not be loaded"):
        load_sfcr(con, project)
    assert con.execute("SELECT COUNT(*) FROM raw_s050102").fetchone() == (0,)


def test_no_files_stops(project, open_warehouse):
    with pytest.raises(IngestError, match="No SFCR files found"):
        load_sfcr(open_warehouse(project), project)


# FR-1.2: the EIOPA file


def test_real_eiopa_file_loads_germany_for_2016_to_2025(real_project, open_warehouse):
    con = open_warehouse(real_project)
    result = load_eiopa(con, real_project)

    assert result.rows_in_table == 921
    assert con.execute("SELECT DISTINCT reporting_country FROM raw_eiopa").fetchall() == [
        ("GERMANY",)
    ]
    periods = [
        p
        for (p,) in con.execute(
            "SELECT DISTINCT reference_period FROM raw_eiopa ORDER BY 1"
        ).fetchall()
    ]
    assert periods == [f"Y{year}" for year in range(2016, 2026)]
    (without_lineage,) = con.execute(
        "SELECT COUNT(*) FROM raw_eiopa WHERE source_file IS NULL OR loaded_at IS NULL"
    ).fetchone()
    assert without_lineage == 0


def test_real_eiopa_values_are_loaded_as_delivered(real_project, open_warehouse):
    con = open_warehouse(real_project)
    load_eiopa(con, real_project)

    # Germany 2025, non-life, gross written premium direct business, as printed in the file.
    assert con.execute(
        "SELECT value FROM raw_eiopa WHERE reference_period = 'Y2025' AND item_code = 'R0110'"
    ).fetchone() == (123498.821642,)
    # Heading rows such as "Premiums written" carry no value: NULL, not zero.
    assert con.execute(
        "SELECT value FROM raw_eiopa WHERE reference_period = 'Y2025' AND item_code = 'R0101'"
    ).fetchone() == (None,)


def test_eiopa_columns_are_found_in_any_order_and_spelling_of_the_long_headers(
    project, open_warehouse
):
    header = [
        "Item code",
        "Value",
        "REFERENCE PERIOD",
        "Reporting country",
        "Business type",
        "Item",
        "Number of submissions",
        "Date of extraction",
    ]
    path = project.eiopa_dir / "SA_Premiums_Claims_Expenses.csv"
    path.write_text(
        ",".join(header) + "\n" + "R0210,12.5,Y2025,Germany,Non-Life,Gross,7,20260101\n"
    )
    con = open_warehouse(project)

    load_eiopa(con, project)

    assert con.execute(
        "SELECT reporting_country, reference_period, item, business_type, item_code, value, "
        "extraction_date, submissions FROM raw_eiopa"
    ).fetchall() == [("Germany", "Y2025", "Gross", "Non-Life", "R0210", 12.5, "20260101", 7)]


def test_changed_eiopa_file_replaces_the_old_rows(project, open_warehouse):
    con = open_warehouse(project)
    load_eiopa(con, project)

    write_eiopa_file(project, market_rows("GERMANY", 2024) + market_rows("GERMANY", 2025))
    result = load_eiopa(con, project)

    assert (result.loaded, result.rows_in_table) == (True, 12)
    assert load_eiopa(con, project).loaded is False


def test_reloading_sfcr_files_leaves_the_eiopa_load_alone(project, open_warehouse):
    write_sfcr_file(project, "Test SE", 2025, balanced_rows())
    con = open_warehouse(project)
    load_eiopa(con, project)

    load_sfcr(con, project)

    assert load_eiopa(con, project).loaded is False
    assert con.execute("SELECT COUNT(*) FROM raw_eiopa").fetchone() == (7,)


def test_missing_eiopa_column_stops_and_names_it(project, open_warehouse):
    header = [name for name in EIOPA_HEADER if name != "Item code"] + ["Code"]
    write_eiopa_file(project, market_rows("GERMANY", 2025), header=header)

    with pytest.raises(IngestError, match="column not found: Item code"):
        load_eiopa(open_warehouse(project), project)


def test_eiopa_file_without_germany_stops_and_lists_the_countries(project, open_warehouse):
    write_eiopa_file(project, market_rows("FRANCE", 2025) + market_rows("DE", 2025))

    with pytest.raises(IngestError, match="no rows for reporting country GERMANY") as stopped:
        load_eiopa(open_warehouse(project), project)
    assert "DE, FRANCE" in str(stopped.value)


def test_missing_eiopa_file_stops_with_the_download_path(project, open_warehouse):
    (project.eiopa_dir / "SA_Premiums_Claims_Expenses.csv").unlink()

    with pytest.raises(IngestError, match="found 0") as stopped:
        load_eiopa(open_warehouse(project), project)
    assert "eiopa.europa.eu" in str(stopped.value)


def test_two_eiopa_files_stop(project, open_warehouse):
    write_eiopa_file(project, market_rows("GERMANY", 2025), name="second.csv")

    with pytest.raises(IngestError, match="found 2"):
        load_eiopa(open_warehouse(project), project)


def test_eiopa_period_that_is_not_a_year_stops_and_loads_nothing(project, open_warehouse):
    write_eiopa_file(project, [("GERMANY", "2025Q4", "Non-Life", "R0210", 1)])
    con = open_warehouse(project)

    with pytest.raises(IngestError, match="not a year like Y2025: 2025Q4"):
        load_eiopa(con, project)
    assert con.execute("SELECT COUNT(*) FROM raw_eiopa").fetchone() == (0,)


def test_eiopa_duplicate_item_stops(project, open_warehouse):
    write_eiopa_file(project, market_rows("GERMANY", 2025) + market_rows("GERMANY", 2025))

    with pytest.raises(IngestError, match="more than one row"):
        load_eiopa(open_warehouse(project), project)


def test_eiopa_text_in_the_value_column_stops(project, open_warehouse):
    write_eiopa_file(project, [("GERMANY", "Y2025", "Non-Life", "R0210", "n/a")])

    with pytest.raises(IngestError, match="could not be loaded"):
        load_eiopa(open_warehouse(project), project)


# FR-1.23: the hand-maintained GDV file


def test_real_gdv_file_passes_validation_and_loads(real_project, open_warehouse):
    con = open_warehouse(real_project)
    load_reference(con, real_project)

    rows = con.execute(
        "SELECT line_group, COUNT(*), MIN(year), MAX(year), MIN(ratio_type), MAX(ratio_type) "
        "FROM ref_market_lob_gdv GROUP BY line_group ORDER BY line_group"
    ).fetchall()
    assert rows == [
        ("Liability", 3, 2022, 2024, "current_year", "current_year"),
        ("Marine, aviation and transport", 3, 2022, 2024, "current_year", "current_year"),
        ("Property", 3, 2022, 2024, "current_year", "current_year"),
    ]
    # As printed: Allgemeine Haftpflichtversicherung 2024, table IV | 79, page 84.
    assert con.execute(
        "SELECT gdv_line, loss_ratio_pct, source_table, source_page FROM ref_market_lob_gdv "
        "WHERE year = 2024 AND line_group = 'Liability'"
    ).fetchone() == ("Allgemeine Haftpflichtversicherung", Decimal("64.50"), "IV | 79", 84)


def test_gdv_file_with_only_a_header_is_valid(project, open_warehouse):
    con = open_warehouse(project)
    load_reference(con, project)

    assert con.execute("SELECT COUNT(*) FROM ref_market_lob_gdv").fetchone() == (0,)


def gdv_row(year=2024, line_group="Liability", gdv_line="Haftpflicht", ratio=64.5, **changes):
    ratio_type, basis, source, table, page = GDV_SOURCE
    row = {
        "year": year,
        "line_group": line_group,
        "gdv_line": gdv_line,
        "loss_ratio_pct": ratio,
        "ratio_type": ratio_type,
        "basis": basis,
        "source": source,
        "source_table": table,
        "source_page": page,
    } | changes
    return tuple(row.values())


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (gdv_row(year="24"), "line 2: year '24' is not a 4-digit year"),
        (gdv_row(line_group="Cyber"), "line 2: line group 'Cyber' is not in lob_groups.csv"),
        (gdv_row(line_group="Total"), "line 2: line group 'Total' is not in lob_groups.csv"),
        (gdv_row(ratio="64,5"), "line 2: loss_ratio_pct '64,5' is not a percentage"),
        (gdv_row(ratio=0.645 * 1000), "is not a percentage between 0 and 300"),
        (gdv_row(ratio_type="gross"), "line 2: ratio_type 'gross' is not one of"),
        (gdv_row(source_page=""), "line 2: source_page is empty"),
        (gdv_row(source_page="p. 84"), "line 2: source_page 'p. 84' is not a number"),
        (gdv_row(source_table=" "), "line 2: source_table is empty"),
    ],
)
def test_gdv_file_problem_stops_with_the_line_number(project, open_warehouse, row, message):
    write_gdv_file(project, [row])

    with pytest.raises(IngestError, match="market_lob_gdv.csv: 1 problem\\.") as stopped:
        load_reference(open_warehouse(project), project)
    assert message in str(stopped.value)


def test_gdv_file_duplicate_year_and_line_group_stops(project, open_warehouse):
    write_gdv_file(project, [gdv_row(), gdv_row(gdv_line="Other name", ratio=70)])

    with pytest.raises(IngestError, match="line 3: 2024 Liability already appears on line 2"):
        load_reference(open_warehouse(project), project)


def test_gdv_file_lists_every_problem(project, open_warehouse):
    write_gdv_file(project, [gdv_row(year="x"), gdv_row(ratio="n/a"), (2024, "Liability")])

    with pytest.raises(IngestError, match="3 problems") as stopped:
        load_reference(open_warehouse(project), project)
    assert "line 4: 2 values, expected 9" in str(stopped.value)


def test_gdv_file_with_a_wrong_header_stops(project, open_warehouse):
    write_gdv_file(project, [], header=("year", "line", "loss_ratio"))

    with pytest.raises(IngestError, match="market_lob_gdv.csv: header does not match"):
        load_reference(open_warehouse(project), project)


def test_missing_gdv_file_stops(project, open_warehouse):
    (project.reference_dir / "market_lob_gdv.csv").unlink()

    with pytest.raises(IngestError, match="Reference file missing"):
        load_reference(open_warehouse(project), project)
