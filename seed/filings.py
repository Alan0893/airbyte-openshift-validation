"""Discover and download filings from SEC EDGAR.

Routes documents to:
  - legal/     → EX-10 commercial agreements (HTML)
  - compliance/ → 10-K, 10-Q, 8-K filings (HTML)

Traps handled (from the proposal's Appendix B):
  - EX-10 also matches EX-101.* XBRL files — match "EX-10." exactly
  - Many EX-10 exhibits are compensation plans — filter by phrase
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from html.parser import HTMLParser
from pathlib import Path

from .edgar_client import EdgarClient
from . import config

logger = logging.getLogger(__name__)


# Phrases that indicate a commercial agreement (vs. compensation plan)
COMMERCIAL_PHRASES = [
    "supply agreement", "license agreement", "distribution agreement",
    "services agreement", "master agreement", "purchase agreement",
    "collaboration agreement", "development agreement", "lease agreement",
    "partnership agreement", "joint venture", "manufacturing agreement",
    "reseller agreement", "subscription agreement", "hosting agreement",
    "technology agreement", "intellectual property", "strategic alliance",
]

# Phrases that indicate a compensation/stock plan (to exclude)
COMPENSATION_PHRASES = [
    "stock plan", "incentive plan", "compensation plan", "equity plan",
    "option agreement", "restricted stock", "deferred compensation",
    "employment agreement", "severance", "bonus plan", "retirement plan",
    "401(k)", "pension", "indemnification agreement",
]

# Filing types for the compliance folder
COMPLIANCE_FORMS = {"10-K", "10-Q", "8-K", "10-K/A", "10-Q/A", "8-K/A"}


@dataclass
class SeedRecord:
    """Metadata for one downloaded document."""
    company: str
    ticker: str
    cik: int
    accession: str
    filing_type: str
    filing_date: str
    period: str
    document_type: str
    filename: str
    source_uri: str
    local_path: str
    checksum: str
    category: str  # "legal" or "compliance"
    size_bytes: int = 0


class _FilingIndexParser(HTMLParser):
    """Extract document entries from an EDGAR filing index page.

    The index table has columns: Seq, Description, Document (link), Type, Size.
    We need the link text from Document (col 2), and Type (col 3).
    """

    def __init__(self):
        super().__init__()
        self._in_td = False
        self._col_idx = 0
        self._current_cell = ""
        self._current_href = ""
        self._row: dict = {}
        self._rows: list[dict] = []
        self._in_row = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._in_row = True
            self._col_idx = 0
            self._row = {}
        elif tag == "td":
            self._in_td = True
            self._current_cell = ""
            self._current_href = ""
        elif tag == "a" and self._in_td:
            for name, val in attrs:
                if name == "href":
                    self._current_href = val.split("/")[-1]

    def handle_endtag(self, tag):
        if tag == "td" and self._in_td:
            self._in_td = False
            cell = self._current_cell.strip()
            if self._col_idx == 0:
                self._row["seq"] = cell
            elif self._col_idx == 1:
                self._row["description"] = cell
            elif self._col_idx == 2:
                self._row["filename"] = self._current_href or cell
            elif self._col_idx == 3:
                self._row["type"] = cell
            elif self._col_idx == 4:
                self._row["size"] = cell
            self._col_idx += 1
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._row.get("filename"):
                self._rows.append(self._row)

    def handle_data(self, data):
        if self._in_td:
            self._current_cell += data

    @property
    def documents(self) -> list[dict]:
        return self._rows


def _is_commercial_agreement(doc_type: str, description: str, content: str) -> bool:
    """Check if an EX-10 document is a commercial agreement, not a comp plan."""
    combined = f"{description} {content[:5000]}".lower()

    for phrase in COMPENSATION_PHRASES:
        if phrase in combined:
            return False

    for phrase in COMMERCIAL_PHRASES:
        if phrase in combined:
            return True

    # If no clear signal, include it — better to have false positives
    # than miss agreements. Manual review can filter later.
    return True


def _is_ex10(doc_type: str) -> bool:
    """Match EX-10.* but not EX-101.* (XBRL files)."""
    doc_type = doc_type.upper().strip()
    return bool(re.match(r"^EX-10(\.\d+)?$", doc_type))


def discover_filings(client: EdgarClient, cik: int, ticker: str, company: str) -> dict:
    """Fetch all recent filings for a company and categorize them.

    Returns a dict with 'legal' and 'compliance' filing lists.
    """
    subs = client.get_submissions(cik)
    recent = subs.get("filings", {}).get("recent", {})

    accessions = recent.get("accessionNumber", [])
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])
    periods = recent.get("reportDate", [])

    result = {"legal": [], "compliance": []}

    for i, acc in enumerate(accessions):
        form = forms[i] if i < len(forms) else ""
        date = dates[i] if i < len(dates) else ""
        primary = primary_docs[i] if i < len(primary_docs) else ""
        period = periods[i] if i < len(periods) else ""

        if form in COMPLIANCE_FORMS:
            result["compliance"].append({
                "accession": acc,
                "form": form,
                "date": date,
                "primary_document": primary,
                "period": period,
            })

    # For legal docs, scan filings that might contain EX-10 exhibits
    # (EX-10 exhibits are attached to 10-K, 10-Q, 8-K filings)
    for filing in result["compliance"][:50]:
        try:
            index_html = client.get_filing_index(cik, filing["accession"])
            parser = _FilingIndexParser()
            parser.feed(index_html)

            for doc in parser.documents:
                if _is_ex10(doc.get("type", "")):
                    result["legal"].append({
                        "accession": filing["accession"],
                        "form": filing["form"],
                        "date": filing["date"],
                        "period": filing["period"],
                        "exhibit_filename": doc["filename"],
                        "exhibit_type": doc["type"],
                        "description": doc.get("description", ""),
                    })
        except Exception as e:
            logger.warning("Failed to parse index for %s/%s: %s", ticker, filing["accession"], e)

    logger.info(
        "%s (%s): %d compliance filings, %d EX-10 exhibits found",
        ticker, company, len(result["compliance"]), len(result["legal"]),
    )
    return result


def download_legal_documents(
    client: EdgarClient,
    cik: int,
    ticker: str,
    company: str,
    exhibits: list[dict],
    dest: Path,
    max_docs: int = 10,
) -> list[SeedRecord]:
    """Download EX-10 exhibits, filtering for commercial agreements."""
    dest.mkdir(parents=True, exist_ok=True)
    records = []

    for exhibit in exhibits[:max_docs * 3]:  # oversample, filter below
        if len(records) >= max_docs:
            break

        filename = exhibit["exhibit_filename"]
        if not filename.lower().endswith((".htm", ".html", ".txt")):
            continue

        try:
            content = client.download_filing_document(cik, exhibit["accession"], filename)
            content_text = content.decode("utf-8", errors="replace")

            if not _is_commercial_agreement(exhibit["exhibit_type"], exhibit.get("description", ""), content_text):
                logger.debug("Skipping comp plan: %s/%s", ticker, filename)
                continue

            safe_name = f"{ticker}_{exhibit['accession']}_{filename}".replace("/", "_")
            out_path = dest / safe_name
            out_path.write_bytes(content)

            records.append(SeedRecord(
                company=company,
                ticker=ticker,
                cik=cik,
                accession=exhibit["accession"],
                filing_type=exhibit["form"],
                filing_date=exhibit["date"],
                period=exhibit.get("period", ""),
                document_type=exhibit["exhibit_type"],
                filename=safe_name,
                source_uri=EdgarClient.filing_url(cik, exhibit["accession"], filename),
                local_path=str(out_path),
                checksum=EdgarClient.sha256(content),
                category="legal",
                size_bytes=len(content),
            ))
            logger.debug("Downloaded legal: %s", safe_name)

        except Exception as e:
            logger.warning("Failed to download %s/%s: %s", ticker, filename, e)

    logger.info("%s: %d legal documents saved", ticker, len(records))
    return records


def download_compliance_documents(
    client: EdgarClient,
    cik: int,
    ticker: str,
    company: str,
    filings: list[dict],
    dest: Path,
    max_docs: int = 10,
) -> list[SeedRecord]:
    """Download primary documents from 10-K, 10-Q, and 8-K filings."""
    dest.mkdir(parents=True, exist_ok=True)
    records = []

    for filing in filings[:max_docs]:
        primary = filing["primary_document"]
        if not primary:
            continue

        try:
            content = client.download_filing_document(cik, filing["accession"], primary)

            safe_name = f"{ticker}_{filing['accession']}_{primary}".replace("/", "_")
            out_path = dest / safe_name
            out_path.write_bytes(content)

            records.append(SeedRecord(
                company=company,
                ticker=ticker,
                cik=cik,
                accession=filing["accession"],
                filing_type=filing["form"],
                filing_date=filing["date"],
                period=filing.get("period", ""),
                document_type=filing["form"],
                filename=safe_name,
                source_uri=EdgarClient.filing_url(cik, filing["accession"], primary),
                local_path=str(out_path),
                checksum=EdgarClient.sha256(content),
                category="compliance",
                size_bytes=len(content),
            ))
            logger.debug("Downloaded compliance: %s", safe_name)

        except Exception as e:
            logger.warning("Failed to download %s/%s: %s", ticker, primary, e)

    logger.info("%s: %d compliance documents saved", ticker, len(records))
    return records
