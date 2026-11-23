.PHONY: seed seed-quick seed-dry-run configure-rag-connectors
PYTHON ?= python3

# Full seed: all 50 companies, 8 quarters of financial data
seed:
	$(PYTHON) -m seed

# Quick test: 5 companies, no financial archives
seed-quick:
	$(PYTHON) -m seed --companies 5 --skip-financial

# Dry run: discover filings without downloading anything
seed-dry-run:
	$(PYTHON) -m seed --dry-run

# Create the RAG scenario's Airbyte sources, destinations, and connections.
# The required *_CONFIG_FILE variables must point to private JSON files.
configure-rag-connectors:
	./scripts/05-configure-rag-connectors.sh
