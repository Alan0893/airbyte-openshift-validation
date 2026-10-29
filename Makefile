.PHONY: seed seed-quick seed-dry-run

# Full seed: all 50 companies, 8 quarters of financial data
seed:
	python -m seed

# Quick test: 5 companies, no financial archives
seed-quick:
	python -m seed --companies 5 --skip-financial

# Dry run: discover filings without downloading anything
seed-dry-run:
	python -m seed --dry-run
