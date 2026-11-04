# EDGAR RAG Demo Runbook

Estimated duration: 10–15 minutes after the cluster and seed data are ready.
This runbook demonstrates the EDGAR RAG path in the `airbyte-validation`
namespace: S3 seed data → Ray/Docling → embeddings → Milvus →
metadata-filtered retrieval.

## Before the demo

- [ ] `oc login` to the target cluster
- [ ] `oc project airbyte-validation`
- [ ] External S3 seed bucket is populated and the S3 smoke test passed
- [ ] `quay-pull`, `milvus-s3-config`, and `edgar-seed-s3` Secrets exist
- [ ] The Ray image digest in the manifests is accessible from the cluster

Check prerequisites without printing Secret contents:

```bash
oc get secret quay-pull milvus-s3-config edgar-seed-s3 \
  -n airbyte-validation
```

## 1. Start the RAG infrastructure

Apply the Milvus and RayCluster resources:

```bash
oc apply -k manifests/rag-pipeline/

oc wait --for=condition=ready pod -l app=milvus \
  -n airbyte-validation --timeout=180s
oc wait --for=condition=ready pod \
  -l 'app in (edgar-rag-head,edgar-rag-worker)' \
  -n airbyte-validation --timeout=300s
```

Confirm the RayCluster and pods are ready:

```bash
oc get raycluster edgar-rag -n airbyte-validation
oc get pods -n airbyte-validation \
  -l 'app in (milvus,milvus-etcd,edgar-rag-head,edgar-rag-worker)'
```

## 2. Run ingestion

Submit the RayJob. It reads `drive/` and `factsheets/` from the configured
S3 prefix, parses HTML and Markdown with Docling, embeds the chunks, and
writes them to the `edgar_filings` Milvus collection.

```bash
oc apply -f manifests/rag-pipeline/rayjob-edgar-pipeline.yaml
oc get rayjob edgar-rag-ingest -n airbyte-validation -w
```

Stop watching with `Ctrl-C` after the job reaches a completed state. If it
fails, inspect the submitter and Ray worker logs:

```bash
oc logs job/edgar-rag-ingest -n airbyte-validation --all-containers 2>/dev/null || true
oc get pods -n airbyte-validation -l 'ray.io/cluster=edgar-rag'
```

## 3. Verify Milvus

Terminal A:

```bash
oc port-forward svc/milvus-milvus 19530:19530 -n airbyte-validation
```

Terminal B:

```bash
python - <<'PY'
from pymilvus import MilvusClient

client = MilvusClient(uri="http://localhost:19530")
print(client.get_collection_stats(collection_name="edgar_filings"))
PY
```

Record the collection row count for the demo notes. A successful run should
contain both filing chunks and fact-sheet chunks.

## 4. Run the retrieval smoke set

Keep the port-forward running and execute the curated query set:

```bash
python - <<'PY'
import json

from pipeline.rag_query import EdgarRAG

with open("demo/queries.json") as f:
    query_set = json.load(f)

rag = EdgarRAG(milvus_host="localhost", milvus_port=19530)
for item in query_set["queries"]:
    hits = rag.search(item["question"], **item["search"])
    categories = sorted({hit["category"] for hit in hits})
    print(f"{item['id']}: {len(hits)} chunks; categories={categories}")
PY
```

What to demonstrate:

- Fact-sheet queries return `category=factsheet` chunks.
- Compliance queries return narrative filing chunks.
- Legal queries filter on `category=legal` for EX-10 exhibits.
- Compliance queries can also filter on `filing_type` (for example, 10-K or
10-Q).
- Mixed queries can retrieve both `factsheet` and filing categories.
- The `aapl-debt-to-equity` check retrieves `$308.0B` and `$57.0B`; the
ratio is computed from those components rather than matched as a substring.

## 5. Optional answer generation

Run `EdgarRAG.ask()` only after an approved OGX/vLLM or other LLM endpoint is
available. Retrieval validation does not require an LLM.

## Evidence to capture

- RayJob completion status and relevant worker logs
- Milvus `edgar_filings` collection statistics
- Query IDs, hit counts, and returned categories
- Representative fact-sheet and filing chunks for the demo narrative

Do not claim end-to-end answer quality or citation correctness until real
answers and retrieved contexts have been captured. EvalHub/RAGAS scoring is a
later step and consumes JSONL with `user_input`, `response`,
`retrieved_contexts`, and `reference` fields.
