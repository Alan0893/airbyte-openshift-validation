"""Seed configuration: company list, output paths, and EDGAR settings."""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# EDGAR access — SEC requires a descriptive User-Agent and ≤10 req/sec.
# Update ORG_NAME and CONTACT_EMAIL before running.
# ---------------------------------------------------------------------------

ORG_NAME = os.environ.get("EDGAR_ORG", "")
CONTACT_EMAIL = os.environ.get("EDGAR_EMAIL", "")
USER_AGENT = f"{ORG_NAME} {CONTACT_EMAIL}".strip()

if not USER_AGENT:
    raise RuntimeError(
        "SEC EDGAR requires a User-Agent with org name and contact email.\n"
        "Set EDGAR_ORG and EDGAR_EMAIL environment variables, e.g.:\n"
        "  export EDGAR_ORG='My Company'\n"
        "  export EDGAR_EMAIL='user@example.com'"
    )

MAX_REQUESTS_PER_SECOND = 8  # stay under SEC's 10/sec hard limit

# ---------------------------------------------------------------------------
# Output directories — all under data/seed/, ignored from Git.
# These mirror the logical source inventory from the proposal:
#   Google Drive legal/        → data/seed/drive/legal/
#   Google Drive compliance/   → data/seed/drive/compliance/
#   S3 archives                → data/seed/s3/financial-statements/
#   PostgreSQL                 → data/seed/postgres/
# ---------------------------------------------------------------------------

SEED_ROOT = Path(__file__).resolve().parent.parent / "data" / "seed"
LEGAL_DIR = SEED_ROOT / "drive" / "legal"
COMPLIANCE_DIR = SEED_ROOT / "drive" / "compliance"
FINANCIAL_ARCHIVES_DIR = SEED_ROOT / "s3" / "financial-statements"
POSTGRES_DIR = SEED_ROOT / "postgres"
MANIFEST_DIR = SEED_ROOT / "manifests"

# ---------------------------------------------------------------------------
# Financial Statement Data Sets — quarterly archives from SEC DERA.
# Cover 8 quarters ending 2024-Q4 (most recent full-year cycle available).
# ---------------------------------------------------------------------------

FINANCIAL_QUARTERS = [
    "2023q1", "2023q2", "2023q3", "2023q4",
    "2024q1", "2024q2", "2024q3", "2024q4",
]

# ---------------------------------------------------------------------------
# Target companies — curated tickers for the counterparty due-diligence
# scenario. CIKs and names are resolved at runtime from SEC's
# company_tickers.json, so nothing goes stale.
#
# Selection criteria:
#   - Large enough to have EX-10 commercial agreements (not just comp plans)
#   - Active filers with recent 10-K, 10-Q, 8-K
#   - Mix of industries relevant to a counterparty review
#   - Well-known enough to be recognizable in a demo
# ---------------------------------------------------------------------------

TICKERS = [
    # Technology
    "AAPL", "MSFT", "GOOG", "AMZN", "CRM",
    "ORCL", "IBM", "CSCO", "INTC", "AMD",
    # Financial services
    "JPM", "BAC", "GS", "MS", "C",
    "WFC", "BLK", "AXP", "SCHW", "USB",
    # Healthcare / pharma
    "JNJ", "PFE", "UNH", "ABBV", "MRK",
    "LLY", "TMO", "ABT", "BMY", "AMGN",
    # Industrial / manufacturing
    "GE", "CAT", "HON", "MMM", "BA",
    "RTX", "LMT", "DE", "EMR", "ITW",
    # Consumer / retail
    "WMT", "PG", "KO", "PEP", "COST",
    "NKE", "MCD", "SBUX", "TGT", "HD",
]


def resolve_companies(tickers: list[str] | None = None) -> list[tuple[str, int, str]]:
    """Resolve tickers to (ticker, CIK, name) from SEC's company_tickers.json.

    Fetched once per run; raises on network failure so bad data
    never silently enters the seed.
    """
    import requests

    tickers = tickers or TICKERS
    resp = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()

    lookup = {}
    for entry in resp.json().values():
        lookup[entry["ticker"].upper()] = (entry["cik_str"], entry["title"])

    companies = []
    for t in tickers:
        key = t.upper()
        if key not in lookup:
            raise ValueError(f"Ticker {t!r} not found in SEC company_tickers.json")
        cik, name = lookup[key]
        companies.append((t, int(cik), name))

    return companies
