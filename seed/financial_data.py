"""Download and extract SEC Financial Statement Data Sets.

Each quarterly archive contains TSV files:
  - sub.txt: one row per filing (adsh, cik, name, form, period, ...)
  - num.txt: one row per reported number (adsh, tag, version, period, value, ...)

We download the ZIP archives (for S3 transfer testing) and extract
SUB/NUM rows filtered to our target companies (for PostgreSQL seeding).
"""

import csv
import io
import json
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .edgar_client import EdgarClient
from . import config

logger = logging.getLogger(__name__)


@dataclass
class FinancialDataSummary:
    """Summary of extracted financial data for a quarter."""
    quarter: str
    archive_path: str
    archive_checksum: str
    archive_size_bytes: int
    sub_rows: int
    num_rows: int


def download_archives(client: EdgarClient) -> list[FinancialDataSummary]:
    """Download all configured quarterly ZIP archives."""
    summaries = []
    dest = config.FINANCIAL_ARCHIVES_DIR
    dest.mkdir(parents=True, exist_ok=True)

    for quarter in config.FINANCIAL_QUARTERS:
        archive = client.download_financial_dataset(quarter, dest)
        content = archive.read_bytes()
        summaries.append(FinancialDataSummary(
            quarter=quarter,
            archive_path=str(archive),
            archive_checksum=EdgarClient.sha256(content),
            archive_size_bytes=len(content),
            sub_rows=0,
            num_rows=0,
        ))

    return summaries


def extract_company_records(
    summaries: list[FinancialDataSummary],
    target_ciks: set[int],
) -> tuple[list[dict], list[dict]]:
    """Extract SUB and NUM rows for target companies from downloaded archives.

    Returns (sub_rows, num_rows) as lists of dicts.
    """
    all_sub = []
    all_num = []
    target_adsh = set()

    for summary in summaries:
        archive_path = Path(summary.archive_path)
        if not archive_path.exists():
            logger.warning("Archive not found: %s", archive_path)
            continue

        logger.info("Extracting %s ...", summary.quarter)

        with zipfile.ZipFile(archive_path, "r") as zf:
            # Extract SUB rows for target companies
            sub_count = 0
            if "sub.txt" in zf.namelist():
                with zf.open("sub.txt") as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
                    for row in reader:
                        try:
                            cik = int(row.get("cik", 0))
                        except (ValueError, TypeError):
                            continue
                        if cik in target_ciks:
                            row["_quarter"] = summary.quarter
                            all_sub.append(row)
                            target_adsh.add(row.get("adsh", ""))
                            sub_count += 1

            # Extract NUM rows matching target filings
            num_count = 0
            if "num.txt" in zf.namelist():
                with zf.open("num.txt") as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
                    for row in reader:
                        if row.get("adsh", "") in target_adsh:
                            row["_quarter"] = summary.quarter
                            all_num.append(row)
                            num_count += 1

            summary.sub_rows = sub_count
            summary.num_rows = num_count
            logger.info("  %s: %d SUB rows, %d NUM rows", summary.quarter, sub_count, num_count)

    logger.info("Total: %d SUB rows, %d NUM rows across %d quarters",
                len(all_sub), len(all_num), len(summaries))
    return all_sub, all_num


def write_postgres_seed(sub_rows: list[dict], num_rows: list[dict], dest: Path):
    """Write SQL seed file for loading SUB and NUM into PostgreSQL."""
    dest.mkdir(parents=True, exist_ok=True)
    sql_path = dest / "financial_seed.sql"

    with open(sql_path, "w") as f:
        f.write("-- Auto-generated SEC financial data seed\n")
        f.write("-- Source: SEC EDGAR Financial Statement Data Sets\n\n")
        f.write("BEGIN;\n\n")

        # SUB table
        f.write("CREATE TABLE IF NOT EXISTS sub (\n")
        f.write("    adsh VARCHAR(20) PRIMARY KEY,\n")
        f.write("    cik INTEGER NOT NULL,\n")
        f.write("    name VARCHAR(200),\n")
        f.write("    sic INTEGER,\n")
        f.write("    countryba VARCHAR(4),\n")
        f.write("    stprba VARCHAR(4),\n")
        f.write("    cityba VARCHAR(50),\n")
        f.write("    form VARCHAR(20),\n")
        f.write("    period INTEGER,\n")
        f.write("    fy INTEGER,\n")
        f.write("    fp VARCHAR(4),\n")
        f.write("    filed INTEGER,\n")
        f.write("    accepted VARCHAR(30),\n")
        f.write("    instance VARCHAR(200),\n")
        f.write("    _quarter VARCHAR(10)\n")
        f.write(");\n\n")

        # NUM table
        f.write("CREATE TABLE IF NOT EXISTS num (\n")
        f.write("    id SERIAL PRIMARY KEY,\n")
        f.write("    adsh VARCHAR(20) NOT NULL REFERENCES sub(adsh),\n")
        f.write("    tag VARCHAR(256) NOT NULL,\n")
        f.write("    version VARCHAR(30),\n")
        f.write("    coreg VARCHAR(256),\n")
        f.write("    ddate INTEGER,\n")
        f.write("    qtrs INTEGER,\n")
        f.write("    uom VARCHAR(30),\n")
        f.write("    value NUMERIC,\n")
        f.write("    footnote TEXT,\n")
        f.write("    _quarter VARCHAR(10)\n")
        f.write(");\n\n")

        f.write("CREATE INDEX IF NOT EXISTS idx_sub_cik ON sub(cik);\n")
        f.write("CREATE INDEX IF NOT EXISTS idx_num_adsh ON num(adsh);\n")
        f.write("CREATE INDEX IF NOT EXISTS idx_num_tag ON num(tag);\n\n")

        # Insert SUB rows
        for row in sub_rows:
            vals = _sql_values([
                row.get("adsh"), row.get("cik"), row.get("name"),
                row.get("sic"), row.get("countryba"), row.get("stprba"),
                row.get("cityba"), row.get("form"), row.get("period"),
                row.get("fy"), row.get("fp"), row.get("filed"),
                row.get("accepted"), row.get("instance"), row.get("_quarter"),
            ])
            f.write(f"INSERT INTO sub VALUES ({vals}) ON CONFLICT (adsh) DO NOTHING;\n")

        f.write("\n")

        # Insert NUM rows
        for row in num_rows:
            vals = _sql_values([
                None,  # serial id
                row.get("adsh"), row.get("tag"), row.get("version"),
                row.get("coreg"), row.get("ddate"), row.get("qtrs"),
                row.get("uom"), row.get("value"), row.get("footnote"),
                row.get("_quarter"),
            ])
            f.write(f"INSERT INTO num VALUES ({vals});\n")

        f.write("\nCOMMIT;\n")

    logger.info("Wrote %s (%d SUB, %d NUM)", sql_path, len(sub_rows), len(num_rows))

    # Also write as TSV for alternative loading
    _write_tsv(dest / "sub.tsv", sub_rows)
    _write_tsv(dest / "num.tsv", num_rows)

    return sql_path


def _sql_values(values: list) -> str:
    """Format a list of values as a SQL VALUES tuple."""
    parts = []
    for v in values:
        if v is None or v == "":
            parts.append("NULL")
        elif isinstance(v, (int, float)):
            parts.append(str(v))
        else:
            try:
                num = float(v)
                if num == int(num):
                    parts.append(str(int(num)))
                else:
                    parts.append(str(num))
            except (ValueError, TypeError):
                escaped = str(v).replace("'", "''")
                parts.append(f"'{escaped}'")
    return ", ".join(parts)


def _write_tsv(path: Path, rows: list[dict]):
    """Write rows as a TSV file."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote %s (%d rows)", path, len(rows))
