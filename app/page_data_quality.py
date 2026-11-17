"""Data quality and definitions page (FR-1.20): reconciliation status, the accounting
basis note and the KPI glossary."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import queries
import ui


def _badge(failures: int, warnings: int) -> None:
    """Status as an icon and a word, never as a color alone."""
    if failures:
        st.badge("Failed", icon=":material/cancel:", color="red")
    elif warnings:
        st.badge("Warning", icon=":material/warning:", color="orange")
    else:
        st.badge("Passed", icon=":material/check_circle:", color="green")


def render(slicers: ui.Slicers) -> None:
    st.title("Data quality and definitions")
    st.caption(f"{slicers.insurer} · {slicers.year}")

    st.subheader("Quality gate")
    st.caption(
        "The model and every page of this cockpit are built only after these checks. "
        "A failed check stops the pipeline; a warning is listed and the run goes on."
    )
    summary = queries.dq_summary()
    for column, (_, check) in zip(st.columns(len(summary)), summary.iterrows(), strict=True):
        with column.container(border=True):
            st.markdown(f"**{check['check_name']}**")
            _badge(int(check["failures"]), int(check["warnings"]))
            st.caption(
                f"{check['requirement']} · {int(check['row_count'])} rows · "
                f"{int(check['failures'])} failed · {int(check['warnings'])} warnings"
            )

    st.subheader(f"Reconciliation, {slicers.insurer} {slicers.year}")
    st.caption(
        "Per row of the template: the lines added up, against the total column. "
        "A gap of up to 3 EUR thousand is rounding in the report. Rows marked "
        "total_only exist in the total column only."
    )
    reconciliation = queries.reconciliation(slicers.insurer, slicers.year)
    counts = reconciliation["status"].value_counts()
    st.markdown(
        " · ".join(f"**{int(count)}** {status}" for status, count in counts.items())
        or "No rows for this insurer and year."
    )
    st.dataframe(
        reconciliation.rename(
            columns={
                "row_code": "Row",
                "line_count": "Lines",
                "sum_lines_teur": "Sum of lines, TEUR",
                "total_teur": "Total column, TEUR",
                "gap_teur": "Gap, TEUR",
                "status": "Status",
            }
        ),
        hide_index=True,
        width="stretch",
        height=280,
    )

    left, right = st.columns([2, 3])
    with left:
        st.subheader("Completeness")
        completeness = queries.completeness()
        if completeness.empty:
            st.markdown("Every insurer has every year and every main line.")
        else:
            st.caption(
                "Missing years or main lines, all insurers. The line group filter does not apply."
            )
            st.dataframe(
                completeness.rename(
                    columns={
                        "check_type": "Check",
                        "insurer": "Insurer",
                        "year": "Year",
                        "line_group": "Line group",
                        "status": "Status",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
    with right:
        st.subheader("Reference values")
        st.caption("GWP in the total column against the figure printed elsewhere in the report.")
        st.dataframe(
            queries.reference_check().rename(
                columns={
                    "insurer": "Insurer",
                    "year": "Year",
                    "metric": "Metric",
                    "reference_value_teur": "Printed, TEUR",
                    "pipeline_value_teur": "Pipeline, TEUR",
                    "gap_teur": "Gap, TEUR",
                    "status": "Status",
                    "source": "Source",
                }
            ),
            hide_index=True,
            width="stretch",
        )

    st.subheader("Accounting basis")
    st.info(ui.HGB_NOTE, icon=":material/info:")
    st.markdown(
        "- Companies are compared on **gross** figures. Net figures are valid within one "
        "company only.\n"
        "- There is no cross-company expense ratio or combined ratio: expenses are net of "
        "reinsurance commissions, and each company books those differently.\n"
        "- Gross claims incurred contain the claims of the year and the reserve changes on "
        "prior years.\n"
        "- A dash in a report is shown as n/a, never as zero."
    )

    st.subheader("KPI glossary")
    st.dataframe(
        queries.kpi_definitions()
        .fillna({"caveat": ""})
        .rename(
            columns={
                "kpi_name": "KPI",
                "formula": "Formula",
                "unit": "Unit",
                "scope": "Scope",
                "caveat": "Caveat",
            }
        ),
        hide_index=True,
        width="stretch",
        height=495,
    )

    with st.expander("Source files"):
        files = queries.source_files()
        st.dataframe(
            pd.DataFrame(
                {
                    "File": files["source_file"],
                    "Rows loaded": files["row_count"],
                    "Loaded at (UTC)": files["loaded_at"],
                }
            ),
            hide_index=True,
            width="stretch",
        )
