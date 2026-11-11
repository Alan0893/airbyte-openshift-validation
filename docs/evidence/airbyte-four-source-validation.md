# Four-source Airbyte landing validation

Run date: 2026-11-10 (UTC; original landing evidence from November 6). Cluster: ai-dev02; namespace:
`airbyte-validation`. Airbyte chart and application: 2.1.1.

## Connections and observed syncs

- Google Drive legal → S3 landing: job 10 succeeded with 144 files and
45,693,114 bytes. Connection runs daily at 00:00 UTC.
- Google Drive compliance → S3 landing: job 12 succeeded with 400 files and
371,469,827 bytes. Connection runs daily at 06:00 UTC.
- PostgreSQL SEC data → PostgreSQL landing: job 13 succeeded with 259,904
records and 57,567,780 bytes. The selected streams are `public.sub` and
`public.num`; the destination has 397 `airbyte_rag.sub` rows and 259,507
`airbyte_rag.num` rows. Full outer joins on each table's key found zero
missing rows and zero mismatched non-Airbyte values. Connection runs daily
at 12:00 UTC.
- S3 financial statements → S3 landing: job 19 succeeded in 4m33s with 32
files and 4,879,024,265 bytes. All 32 landed files match the source sizes
and SHA-256 hashes in
[financial-tsv-sha256.json](financial-tsv-sha256.json). The complete landing
generation is
`airbyte/landing/financial_statement_tsv_files/2026_11_06_1793992449467_/`.
The one-file pilot, job 15, also matched its source hash. Connection runs
daily at 18:00 UTC.

Airbyte landing contains complete legal, compliance, and financial generations, along with older pilot/partial generations. Reconciliation used only the complete generations; older objects should be cleaned up or excluded by consumers.

## Unattended scheduled runs

The jobs below started at their configured daily cron times. All 12 scheduled
jobs succeeded; no failed or canceled job appears in this window.

| Connection | 2026-11-07 | 2026-11-08 | 2026-11-09 |
| --- | --- | --- | --- |
| Legal Drive, 00:00 UTC | 20 succeeded | 24 succeeded | 28 succeeded |
| Compliance Drive, 06:00 UTC | 21 succeeded | 25 succeeded | 29 succeeded |
| PostgreSQL SEC, 12:00 UTC | 22 succeeded | 26 succeeded | 30 succeeded |
| Financial S3, 18:00 UTC | 23 succeeded | 27 succeeded | 42 succeeded |

The full-refresh jobs reported the same byte counts each day: 45,693,114
legal, 371,469,827 compliance, 57,567,780 PostgreSQL, and 4,879,024,265
financial. Internal attempt history showed one successful attempt for each of
the 12 scheduled jobs, with no retryable failures.

## Financial source format and retry evidence

The SEC source archives are ZIP files. Source S3 connector 4.16.4 expands ZIP
members during listing, so the raw-file stream with a `*.zip` glob selected
no files (job 14 failed). The working stream uses extracted
`financial-statements/<quarter>/<table>.tsv` objects, matched by
`financial-statements/**/*.tsv` and copied using raw file transfer. The
source `format` field is required by the connector schema, but raw transfer
does not parse TSV columns.
The checked-in staging helper regenerated the 32-file manifest from the
original local ZIPs byte-for-byte in `--manifest-only` mode.

The final 32-file financial sync succeeded after the approved memory settings
and required Airbyte component restarts were applied. Its replication pod ran
under `restricted-v2` SCC with a 512 MiB request and 2 GiB limit on the
orchestrator, source, and destination containers. A later same-version Helm
upgrade to revision 14 also completed successfully, and post-upgrade legal
validation job 53 passed with 144 files and 45,693,114 bytes.

## Validation status

All four scheduled source connections completed successfully and were
reconciled during the validation window. Incremental behavior remains a
qualified result; see [s4-incremental-validation.md](s4-incremental-validation.md).
Platform-check details, including SCC evidence and API access classification,
are recorded in [platform-checks.md](platform-checks.md). The Google Drive
source-change trace is recorded in
[s7-source-change-validation.md](s7-source-change-validation.md).
