# Financial performance steering cockpit.
# First time: make setup. Then: make all.

# The interpreter used to create the environment. Needs Python 3.11 or newer.
BOOTSTRAP_PYTHON ?= python3.12
PYTHON := .venv/bin/python

.PHONY: setup all pipeline excel docs app test lint format clean

setup:  ## Create .venv and install the project with its dev tools
	$(BOOTSTRAP_PYTHON) -m venv .venv
	$(PYTHON) -m pip install --quiet --upgrade pip
	$(PYTHON) -m pip install --quiet -e ".[dev]"

all: pipeline excel docs  ## Rebuild everything from data/raw

pipeline:  ## Load the raw files, run the quality gate, build the model and the views
	$(PYTHON) -m cockpit.pipeline

excel: pipeline  ## Write exports/cockpit_marts.xlsx with the KPIs as formulas
	$(PYTHON) -m cockpit.export_excel

docs: pipeline  ## Write docs/kpi_definitions.md from the kpi_definitions table
	$(PYTHON) -m cockpit.kpi_docs

app: pipeline  ## Open the dashboard in the browser (stop it with Ctrl+C)
	$(PYTHON) -m streamlit run app/cockpit_app.py

test:  ## Run the tests
	$(PYTHON) -m pytest

lint:  ## Check code style and formatting
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:  ## Fix formatting and import order
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

clean:  ## Delete the warehouse and the exports (both are rebuilt by make all)
	rm -rf warehouse exports
