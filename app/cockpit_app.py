"""The steering cockpit as a Streamlit app (FR-1.17 to FR-1.20).

Run after the pipeline: streamlit run app/cockpit_app.py

Five pages on the SQL views of the warehouse. The slicers in the sidebar apply
to every page, and every page ends with the accounting basis note.
"""

from __future__ import annotations

import streamlit as st

import page_data_quality
import page_line_of_business
import page_overview
import page_peer_market
import page_summary
import queries
import ui

st.set_page_config(page_title="Steering cockpit", page_icon=":material/monitoring:", layout="wide")

if not queries.warehouse_exists():
    st.error(
        "The warehouse does not exist yet. Build it first with `make all` "
        "(or `python -m cockpit.pipeline`), then reload this page."
    )
    st.stop()

ui.apply_style()
slicers = ui.sidebar_slicers()
ui.apply_presentation_style()
ui.masthead(slicers)

page = st.navigation(
    [
        st.Page(
            lambda: page_summary.render(slicers),
            title="Executive summary",
            icon=":material/summarize:",
            url_path="summary",
            default=True,
        ),
        st.Page(
            lambda: page_overview.render(slicers),
            title="Overview",
            icon=":material/dashboard:",
            url_path="overview",
        ),
        st.Page(
            lambda: page_line_of_business.render(slicers),
            title="Line of business",
            icon=":material/stacked_line_chart:",
            url_path="line-of-business",
        ),
        st.Page(
            lambda: page_peer_market.render(slicers),
            title="Peer and market",
            icon=":material/compare_arrows:",
            url_path="peer-and-market",
        ),
        st.Page(
            lambda: page_data_quality.render(slicers),
            title="Data quality and definitions",
            icon=":material/fact_check:",
            url_path="data-quality",
        ),
    ],
    position="top",
)
page.run()
ui.footer()
