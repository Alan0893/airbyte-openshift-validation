"""Seed the four source systems from SEC EDGAR.

Usage:
    python -m seed                  # full seed (all companies, all quarters)
    python -m seed --companies 5    # quick test with 5 companies
    python -m seed --skip-financial  # skip the large ZIP downloads
    python -m seed --dry-run        # discover filings without downloading
"""

import argparse
import logging
import sys
import time

from . import config
from .edgar_client import EdgarClient
from .filings import discover_filings, download_legal_documents, download_compliance_documents
from .financial_data import download_archives, extract_company_records, write_postgres_seed
from .manifest import write_manifest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed")


def main():
    parser = argparse.ArgumentParser(description="Seed source systems from SEC EDGAR")
    parser.add_argument(
        "--companies", type=int, default=len(config.TICKERS),
        help=f"Number of companies to process (default: {len(config.TICKERS)})",
    )
    parser.add_argument(
        "--max-legal", type=int, default=5,
        help="Max legal documents per company (default: 5)",
    )
    parser.add_argument(
        "--max-compliance", type=int, default=8,
        help="Max compliance documents per company (default: 8)",
    )
    parser.add_argument(
        "--skip-financial", action="store_true",
        help="Skip downloading Financial Statement Data Set archives",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Discover filings but don't download documents",
    )
    args = parser.parse_args()

    all_companies = config.resolve_companies()
    companies = all_companies[:args.companies]
    logger.info("Seeding %d companies (resolved %d from SEC)", len(companies), len(all_companies))

    client = EdgarClient()
    all_legal = []
    all_compliance = []
    start = time.monotonic()

    # ----- Phase 1: Discover and download filings -----
    for i, (ticker, cik, company) in enumerate(companies, 1):
        logger.info("[%d/%d] Processing %s (%s, CIK %d)", i, len(companies), company, ticker, cik)

        try:
            filings = discover_filings(client, cik, ticker, company)
        except Exception as e:
            logger.error("Failed to discover filings for %s: %s", ticker, e)
            continue

        if args.dry_run:
            logger.info(
                "  [dry-run] Would download up to %d legal, %d compliance",
                min(len(filings["legal"]), args.max_legal),
                min(len(filings["compliance"]), args.max_compliance),
            )
            continue

        legal = download_legal_documents(
            client, cik, ticker, company,
            filings["legal"], config.LEGAL_DIR,
            max_docs=args.max_legal,
        )
        all_legal.extend(legal)

        compliance = download_compliance_documents(
            client, cik, ticker, company,
            filings["compliance"], config.COMPLIANCE_DIR,
            max_docs=args.max_compliance,
        )
        all_compliance.extend(compliance)

    # ----- Phase 2: Financial Statement Data Sets -----
    financial_summaries = []
    sub_count = 0
    num_count = 0

    if not args.skip_financial and not args.dry_run:
        logger.info("Downloading Financial Statement Data Sets (%d quarters)", len(config.FINANCIAL_QUARTERS))
        financial_summaries = download_archives(client)

        target_ciks = {cik for _, cik, _ in companies}
        sub_rows, num_rows = extract_company_records(financial_summaries, target_ciks)
        sub_count = len(sub_rows)
        num_count = len(num_rows)

        if sub_rows:
            write_postgres_seed(sub_rows, num_rows, config.POSTGRES_DIR)

    # ----- Phase 3: Write manifest -----
    if not args.dry_run:
        write_manifest(all_legal, all_compliance, financial_summaries, sub_count, num_count,
                       company_count=len(companies))

    elapsed = time.monotonic() - start
    logger.info("Done in %.1f seconds", elapsed)


if __name__ == "__main__":
    main()
