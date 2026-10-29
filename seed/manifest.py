"""Generate the seed manifest — connects every output to its source."""

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)


def write_manifest(
    legal_records: list,
    compliance_records: list,
    financial_summaries: list,
    sub_count: int,
    num_count: int,
    company_count: int = 0,
):
    """Write the seed manifest JSON."""
    config.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = config.MANIFEST_DIR / "seed-manifest.json"

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "user_agent": config.USER_AGENT,
            "companies": company_count,
            "financial_quarters": config.FINANCIAL_QUARTERS,
        },
        "summary": {
            "legal_documents": len(legal_records),
            "compliance_documents": len(compliance_records),
            "financial_archives": len(financial_summaries),
            "postgresql_sub_rows": sub_count,
            "postgresql_num_rows": num_count,
            "total_documents": len(legal_records) + len(compliance_records),
        },
        "legal": [asdict(r) for r in legal_records],
        "compliance": [asdict(r) for r in compliance_records],
        "financial_archives": [
            {
                "quarter": s.quarter,
                "archive_path": s.archive_path,
                "archive_checksum": s.archive_checksum,
                "archive_size_bytes": s.archive_size_bytes,
                "sub_rows": s.sub_rows,
                "num_rows": s.num_rows,
            }
            for s in financial_summaries
        ],
    }

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Wrote manifest: %s", manifest_path)

    # Print summary
    print("\n" + "=" * 60)
    print("SEED SUMMARY")
    print("=" * 60)
    print(f"  Companies:            {company_count}")
    print(f"  Legal documents:      {len(legal_records)}")
    print(f"  Compliance documents: {len(compliance_records)}")
    print(f"  Financial archives:   {len(financial_summaries)}")
    print(f"  PostgreSQL SUB rows:  {sub_count:,}")
    print(f"  PostgreSQL NUM rows:  {num_count:,}")
    print(f"  Manifest:             {manifest_path}")
    print("=" * 60)

    return manifest_path
