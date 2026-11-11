# S4 incremental-sync validation

Run date: 2026-11-10 (UTC). Cluster: ai-dev02; namespace:
`airbyte-validation`. Airbyte application: 2.1.1.

## Scope

This is an isolated PostgreSQL test connection. It does not change any of the
four production RAG connections, which remain full-refresh overwrite:

- Connection: `S4 Test - PostgreSQL Customers Incremental`
- Connection ID: `610586cb-5a49-4e4e-b3ad-ab7bee8e6143`
- Source stream: `public.customers`
- Sync mode: `incremental_append`
- Cursor: `created_at`
- Primary key: `id`
- Destination table: `s4_test___STREAM_NAME_`.customers

The destination namespace contains the literal `${STREAM_NAME}` form because
the Public API did not expand that variable for this self-managed connection.
It is isolated from the production `airbyte_rag` schema.

## Observed runs

| Test | Job | Result | Airbyte rows/bytes | Landing observation |
| --- | ---: | --- | ---: | --- |
| Initial incremental baseline | 31 | succeeded | 10 / 1,530 | 10 source rows landed |
| No source change | 32 | succeeded | 1 / 147 | The latest cursor-boundary row (`id=10`) was re-emitted; landing grew to 11 rows |
| Insert `id=990001` at `2099-01-01` | 33 | succeeded | 2 / 306 | New row landed; the cursor-boundary row was also re-emitted; landing grew to 13 rows |
| Update `id=990001` at `2100-01-01` | 34 | succeeded | 1 / 167 | Updated row landed as a second append version; landing grew to 14 rows |
| Delete `id=990001` from source | 35 | succeeded | 0 / 0 | No delete event; both historical versions remained in the landing table |

The source test row was deleted after the update check. The destination retains
the two test versions as evidence of append behavior.

## Result

This validates that the PostgreSQL cursor-based incremental source detects a
new row and a modified row whose cursor advances. It does **not** pass the
full S4 requirement:

- Strict no-resend behavior: **not demonstrated**. The connector re-emitted
  the row at the current cursor boundary on an unchanged run.
- Delete propagation: **not supported by this `incremental_append` test**.
- Rename behavior: **not tested**. Rename semantics apply to file sources and
  need a separate file-connector test.
- Retry behavior: job 54 tested a disposable invalid PostgreSQL destination.
  Airbyte failed once with `failureType: config_error` and `retryable: false`;
  no automatic retry occurred. Transient runtime-failure retry behavior
  remains untested.
- File-source setup: the S3 source catalog exposes
  `incremental_append` with `_ab_source_file_last_modified`, but the Airbyte
  2.1.1 Public API rejected the valid connector cursor as a selectable field.
  The equivalent internal UI API accepted the discovered catalog with field
  selection disabled, allowing the S3 test below to run.

The four production RAG connections remain unchanged and still use
full-refresh overwrite. The S3 file-source follow-up is recorded below.

## S3 file-source test

The Airbyte 2.1.1 public API rejected the S3 connector's internal
`_ab_source_file_last_modified` cursor as a selected field. The same
configuration was created through Airbyte's internal UI API using the
discovered catalog with field selection disabled:

- Connection: `S4 UI Test - S3 Files Incremental`
- Connection ID: `1269f445-b706-4f75-bfd4-f6eb01d38907`
- Source prefix: `s4-ui-test/`
- Sync mode: `incremental_append`
- Cursor: `_ab_source_file_last_modified`
- Destination prefix: `s4_s3_ui_test_`

The source began with two disposable TSV objects, `report-a.tsv` and
`report-b.tsv`.

| Test | Job | Result | Airbyte rows/bytes | Observation |
| --- | ---: | --- | ---: | --- |
| Initial baseline | 37 | succeeded | 2 / 42 | Both files landed under the isolated S3 prefix |
| No source change | 38 | succeeded | 0 / 0 | No files were re-sent |
| Add `report-c.tsv` | 39 | succeeded | 1 / 17 | New file landed |
| Modify `report-a.tsv` | 40 | succeeded | 1 / 22 | Modified file landed |
| Delete `report-b.tsv` | 41 | succeeded | 0 / 0 | No delete event; the old landing object remained |
| Rename `report-c.tsv` → `report-d.tsv` | 43 | succeeded | 1 / 17 | New `report-d.tsv` landed; the old `report-c.tsv` landing object remained |

`report-b.tsv` was removed from the source before job 41 was queued. Rename
job 43 copied `report-c.tsv` to `report-d.tsv` and removed the source
`report-c.tsv`. The source now contains `report-a.tsv` and `report-d.tsv`,
while the landing retains historical objects for `report-b.tsv` and
`report-c.tsv`.

## S4 disposition

The incremental validation is complete for the isolated PostgreSQL and S3
tests, but S4 is a **qualified/partial result**, not a full pass:

- No-resend, new-file, and modified-file behavior passed in the S3 test.
- Rename was recorded as a new landing object; the old landing object was
  retained.
- Deletes were not propagated by `incremental_append`.
- A disposable invalid PostgreSQL destination was used for job 54. Airbyte
  failed after one attempt with `failureType: config_error` and
  `retryable: false`; no automatic retry was created. This confirms that
  configuration failures are not retried automatically. A transient runtime
  failure retry remains untested.

The four production RAG connections remain unchanged and continue to use
full-refresh overwrite.
