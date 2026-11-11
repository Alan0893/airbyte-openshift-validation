# S7 source-change validation

Run date: 2026-11-10 (UTC). Cluster: ai-dev02; namespace:
`airbyte-validation`. Airbyte: 2.1.1. RAG collection: `edgar_filings`.

This disposable test traces a Google Drive file change through Airbyte, the
S3 landing bucket, the S3-to-RAG input mapping, Docling/embedding, Milvus,
and `EdgarRAG.search()`.

## Source and landing evidence

- Connection: Google Drive legal → S3 landing
- Connection ID: `1d0c6793-2e51-4215-8664-8bd5ca61ed69`
- Test file: `S7-validation-20261110.htm`
- Airbyte job 55 succeeded with 145 records and 45,693,501 bytes.
- V1 landed at:
  `airbyte/landing/legal/2026_11_10_1794343237707_/S7-validation-20261110.htm`
- V1 size/hash: 387 bytes, SHA-256
  `a477257e24e80f7acf484c94f0b305b3d0d4b04787319617d68c6663c6112584`.
- The V1 object contained `S7_DRIVE_CHANGE_TEST_20261110_V1`.

The RAG loader expects `edgar-seed/drive/legal/`, while Airbyte writes to
`airbyte/landing/legal/`. For this isolated test, only the disposable object
was copied to `edgar-s7-test/drive/legal/`; the existing seed manifest was
copied to the corresponding test prefix. The production seed prefix and
existing Milvus collection were not replaced.

## RAG indexing and V1 retrieval

- RayJob `edgar-rag-s7-ingest-5` completed successfully in append mode.
- Input: 1 S3 document, 1 legal document, 1 Docling chunk.
- The query `S7_DRIVE_CHANGE_TEST_20261110_V1` returned
  `S7-validation-20261110.htm` as the top legal result with score
  `0.646898`.

## Source change and V2 retrieval

The same Drive file was changed from V1 to V2 and resynced.

- Airbyte job 56 succeeded with 145 records and 45,693,502 bytes.
- V2 landed at:
  `airbyte/landing/legal/2026_11_10_1794344144712_/S7-validation-20261110.htm`
- V2 size/hash: 388 bytes, SHA-256
  `78f6677239035f5a97e828d2ca2ebdd84ffa761d703c0e501ab9f68291792ca3`.
- The V2 object contained `S7_DRIVE_CHANGE_TEST_20261110_V2` and no V1
  marker.
- RayJob `edgar-rag-s7-ingest-6` completed successfully in append mode with
  1 document and 1 chunk.
- The query `S7_DRIVE_CHANGE_TEST_20261110_V2` returned the V2 text from
  `S7-validation-20261110.htm` as the top legal result with score `0.710484`.
  The older V1 chunk remained second with score `0.643154`, which is expected
  for this append-only isolated test.

## Result and limitation

The source-change path is proven through retrieval:

Google Drive change → Airbyte sync → S3 landing change → RAG input mapping →
Docling/embedding → Milvus → V2 top retrieval.

This is a **qualified/partial S7 result**, not a full answer-level pass. The
current validation has no OGX/vLLM endpoint, so an LLM-generated later answer
and citation update were not tested. The isolated append run also retains the
prior V1 chunk; stale-vector cleanup is outside this test and remains a
separate lifecycle consideration.
