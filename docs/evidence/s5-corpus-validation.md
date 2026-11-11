# S5 corpus-contract validation

Run date: 2026-11-11 (UTC). Cluster: ai-dev02; namespace:
`airbyte-validation`.

## Prepared corpus

The prepared corpus is organized under the single S3 root prefix
`s3://ai-dev02-bucket01-data/edgar-seed/`:

```text
edgar-seed/
  drive/legal/
  drive/compliance/
  factsheets/
  manifests/seed-manifest.json
```

The checked-in source layout is the same under `data/seed/`.

- Legal filings: 144 HTML files.
- Compliance filings: 400 HTML files.
- Derived fact sheets: 49 Markdown files.
- Total prepared local documents: 593.
- All 593 document filenames are unique across the legal, compliance, and
  fact-sheet directories.
- `seed-manifest.json` contains 144 legal entries, 400 compliance entries,
  eight financial archive records, and PostgreSQL source row counts of 397
  `SUB` rows and 259,507 `NUM` rows.
- `demo/queries.json` contains 11 unique stable query IDs covering fact-sheet,
  compliance, legal, mixed, and negative cases.

## Indexing evidence

The full baseline RAG index contained 43,219 Milvus rows:

- 4,735 legal chunks
- 38,244 compliance chunks
- 240 fact-sheet chunks

Two isolated S7 source-change chunks were appended afterward for the V1 and
V2 retrieval trace, bringing the current `edgar_filings` collection count to
43,221. The S7 rows are validation artifacts, not additional seed-corpus
documents.

## AutoRAG contract status

This is a partial S5 result. The source manifest, consolidated S3 root prefix,
unique filenames, derived fact sheets, and stable demo query IDs are present.
The final AutoRAG/RAGAS evaluation package is not yet produced. In particular,
the JSONL fields `user_input`, `response`, `retrieved_contexts`, and
`reference` are not finalized with matching evaluation IDs and references.
Generated responses and citation-ready references also depend on the deferred
OGX/vLLM answer path.
