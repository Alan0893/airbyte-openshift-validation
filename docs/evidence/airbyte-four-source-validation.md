# Four-source Airbyte landing validation

Run date: 2026-11-06 (UTC). Cluster: ai-dev02; namespace:
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

The Drive landing inventory has a 144-file legal generation and a 400-file
compliance generation under `airbyte/landing/`. Earlier one-file pilot
generations also remain there; count only the full generations above.
The S3 financial landing likewise contains a one-file pilot generation and a
17-file partial generation left by the OOM run. Consumers must select the
complete generation until those older objects are deliberately cleaned up.

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

The first 32-file run (job 16) was canceled after its source container was
OOM-killed at the default 512 MiB limit; it left a partial 17-file landing
generation. A 512 MiB request and 2 GiB limit were applied with Airbyte's
pinned 2.1.1 Helm chart. Job 17 was canceled before processing because the
workload launcher still had the old ConfigMap values. After restarting that
launcher, job 18 was also canceled before processing: its replication pod
still had a 512 MiB limit. The worker, workload API, and server also needed
restarts to read their updated environment values. Helm revision 13 explicitly
sets the workload API's memory environment values. Job 19's replication pod
was confirmed under `restricted-v2` SCC with a 512 MiB request and 2 GiB
limit on its orchestrator, source, and destination containers.

## Remaining validation

- Job 19's `restricted-v2` SCC is recorded above. Capture SCC and UID for the
next legal, compliance, and PostgreSQL sync pods to complete P3 evidence.
- All 12 scheduled jobs succeeded across November 7–9, with one successful
  attempt each; S2 is now a pass for this validation window.
- The production connections use full-refresh overwrite. An isolated
  PostgreSQL `incremental_append` test detected an inserted row and a modified
  row, but re-emitted the current cursor-boundary row on an unchanged run and
  did not propagate a delete. See
  [s4-incremental-validation.md](s4-incremental-validation.md). File-source
  incremental behavior now has an isolated S3 result: unchanged sync emitted
  zero rows, add/modify each emitted one row, and rename emitted one new row
  while retaining the old landing object. Delete emitted zero rows and did
  not remove the old landing object; retry behavior remains open, so S4 is a
  qualified/partial result rather than a full pass.
- The Airbyte Public API route accepted requests without an authentication
token during this run, including connection updates. Classify its access
control separately from the web UI login check (P7).
