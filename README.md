# Airbyte on OpenShift AI: EDGAR data validation

This repository records a partner validation of Airbyte 2.1.1 on OpenShift 4.21.16 and Red Hat OpenShift AI 3.5.2. It includes four scheduled SEC data connections, source-to-destination checks, a prepared EDGAR corpus, and Ray/Docling ingestion into Milvus. The current result is searchable retrieval with source metadata.

The Airbyte landing paths and the Ray input prefix are separate. We copied one changed Google Drive test file between them to trace a source update through retrieval; the routine handoff is not automated. LLM answers, citations, and AutoRAG evaluation were deferred for this validation stage.

An earlier OpenShift AI 3.4.1 platform validation is retained in the [validation report](reports/validation-report.md) and [certification results](docs/certification.md).

## Recorded results

- **Airbyte landing:** Two Google Drive folders, an S3 financial-file source, and PostgreSQL SEC tables ran as four daily connections. The complete landing generations contain 144 legal HTML files, 400 compliance HTML files, 32 financial TSV files, 397 `SUB` rows, and 259,507 `NUM` rows. Drive file counts and bytes, financial TSV sizes and SHA-256 hashes, and PostgreSQL keys and selected values were checked against the sources. See the [four-source evidence](docs/evidence/airbyte-four-source-validation.md).
- **Unattended operation:** All 12 scheduled runs in the November 7–9, 2026 observation window succeeded on their first attempt. A controlled restart during a sync and a same-version Helm upgrade were also tested. See the [platform checks](docs/evidence/platform-checks.md).
- **Retrieval:** The prepared corpus contains 144 legal filings, 400 compliance filings, and 49 derived Markdown fact sheets. The first Milvus index held 43,219 passages; two source-change test passages brought the observed collection count to 43,221. The [11 demo queries](demo/queries.json) cover fact-sheet, legal, compliance, mixed, and empty-result cases. See the [corpus evidence](docs/evidence/s5-corpus-validation.md) and [retrieval runbook](demo/demo-runbook.md).
- **Source change:** One Google Drive test file was synced, copied manually into an isolated Ray input, re-indexed after an edit, and retrieved with the new text. Its earlier vector remained in the index. See the [source-change evidence](docs/evidence/s7-source-change-validation.md).

The [validation report](reports/validation-report.md) records the full S1–S8 and P1–P9 results. Incremental file deletes and renames left older S3 landing objects, and the current Airbyte deployment has qualified chart, RBAC, storage, and Public API findings. Larger-load quota testing, answer generation, and AutoRAG scoring were deferred by agreement.

The installation is a qualified validation result, not a Red Hat certification. The earlier [preflight and chart-verifier checks](docs/certification.md) record the packaging gaps.

## Data paths

```text
Google Drive legal/compliance ─┐
S3 financial TSV files ────────┴─→ Airbyte ─→ S3 landing
PostgreSQL SUB/NUM ───────────────→ Airbyte ─→ PostgreSQL landing

Curated EDGAR seed in S3 ─→ Ray + Docling ─→ embeddings ─→ Milvus ─→ search
       ↑
       └── one Airbyte-landed Drive file copied manually for the source-change test
```

The curated seed contains HTML filings, fact sheets rendered from `SUB`/`NUM`, and a source manifest. `category`, `ticker`, and `filing_type` metadata distinguish evidence types within the `edgar_filings` Milvus collection.

## Repository guide

- [Deployment guide](docs/deployment-guide.md), [Helm values](helm/openshift-values.yaml), and [Airbyte connector templates](examples/airbyte/rag-connectors/README.md) cover installation and source setup.
- [Seed generator](seed/) downloads selected public SEC filings and financial statement data sets. [Fact-sheet renderer](pipeline/factsheet.py) turns the structured records into Markdown. The generated `data/seed/` corpus is ignored by Git.
- [Ray pipeline](pipeline/README.md) and [OpenShift manifests](manifests/rag-pipeline/) cover S3 input, Docling, embeddings, and Milvus. The Ray image is pinned by digest in the cluster manifests.
- [Evidence](docs/evidence/) and the [validation report](reports/validation-report.md) contain the recorded checks and limitations.
- [Demo runbook](demo/demo-runbook.md) shows the existing RayJob and retrieval results. The [earlier platform demo script](demo/demo-script.md) and [dashboard](demo/dashboard.html) describe the August baseline.

## Generate the seed corpus

From the repository root, install the dependencies in `seed/requirements.txt`, set a descriptive SEC contact identity, then run:

```bash
export EDGAR_ORG="Your Organization"
export EDGAR_EMAIL="you@example.com"
make seed
python3 -m pipeline.factsheet
```

`make seed` downloads a large corpus into the ignored `data/seed/` directory. `make seed-quick` limits the filing selection for a smaller local check. The [pipeline guide](pipeline/README.md) describes S3 staging and the Docling smoke test before a new cluster ingestion.

Do not commit filled connector configs or credentials. The checked-in `*.example` files are templates.
