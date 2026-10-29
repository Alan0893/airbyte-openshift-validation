"""Rate-limited HTTP client for SEC EDGAR.

SEC requires:
  - A descriptive User-Agent (org name + contact email)
  - No more than 10 requests per second
  - Graceful handling of 403 (rejected User-Agent) and 429 (rate limit)

References:
  https://www.sec.gov/os/accessing-edgar-data
  https://www.sec.gov/search#/dateRange=custom
"""

import hashlib
import logging
import time
from pathlib import Path

import requests

from . import config

logger = logging.getLogger(__name__)


class EdgarClient:
    """Rate-limited client for SEC EDGAR APIs and file downloads."""

    SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
    ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
    EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
    DERA_BASE = "https://www.sec.gov/files/dera/data/financial-statement-data-sets"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        })
        self._min_interval = 1.0 / config.MAX_REQUESTS_PER_SECOND
        self._last_request_time = 0.0

    def _throttle(self):
        """Sleep if needed to stay under the rate limit."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        """Rate-limited GET with retry on 429."""
        self._throttle()
        resp = self.session.get(url, timeout=30, **kwargs)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 10))
            logger.warning("Rate limited (429), sleeping %ds", retry_after)
            time.sleep(retry_after)
            return self.get(url, **kwargs)

        if resp.status_code == 403:
            raise RuntimeError(
                f"SEC rejected request (403). Check User-Agent in config.py. "
                f"Current: {config.USER_AGENT!r}"
            )

        resp.raise_for_status()
        return resp

    def get_submissions(self, cik: int) -> dict:
        """Fetch a company's filing submissions by CIK."""
        padded = str(cik).zfill(10)
        url = f"{self.SUBMISSIONS_BASE}/CIK{padded}.json"
        return self.get(url).json()

    def get_filing_index(self, cik: int, accession: str) -> str:
        """Fetch a filing's index page (lists all documents and their types)."""
        acc_no_dashes = accession.replace("-", "")
        url = f"{self.ARCHIVES_BASE}/{cik}/{acc_no_dashes}/{accession}-index.html"
        return self.get(url).text

    def download_filing_document(self, cik: int, accession: str, filename: str) -> bytes:
        """Download a specific document from a filing."""
        acc_no_dashes = accession.replace("-", "")
        url = f"{self.ARCHIVES_BASE}/{cik}/{acc_no_dashes}/{filename}"
        return self.get(url).content

    def download_financial_dataset(self, quarter: str, dest: Path) -> Path:
        """Download a quarterly Financial Statement Data Set ZIP archive."""
        url = f"{self.DERA_BASE}/{quarter}.zip"
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = dest / f"{quarter}.zip"

        if out.exists():
            logger.info("Already downloaded: %s", out.name)
            return out

        logger.info("Downloading %s ...", url)
        resp = self.get(url)
        out.write_bytes(resp.content)
        logger.info("Saved %s (%s bytes)", out.name, f"{len(resp.content):,}")
        return out

    @staticmethod
    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def filing_url(cik: int, accession: str, filename: str) -> str:
        acc_no_dashes = accession.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/{filename}"
