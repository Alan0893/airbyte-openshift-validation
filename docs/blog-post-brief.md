# Blog Post Brief: Financial Document Intake with Airbyte + OpenShift AI

Handoff doc for whoever writes the post. Covers the concept, what this repo can
actually back up with evidence, and what would need to be built or sourced
elsewhere.

---

## If you are an AI agent drafting from this

Read this section first.

**You need the repo.** Every file path below is relative to this document
inside the `airbyte-openshift-validation` repo. If you were handed this brief
as a standalone file with no repo access, say so and stop -- the evidence
tables cite sources you cannot open, and the post will be wrong if you fill
them in from memory.

**Rules for the draft:**

1. Only the "Evidence inventory" section is proven. Any claim not traceable to
   a file in the source material table is unproven -- either label it as
   proposed architecture or leave it out. Do not invent metrics, versions,
   timings, or test results.
2. Everything in "Gaps between the concept and the repo" must stay visible in
   the outline. AutoRAG in particular is *entirely* net-new -- nothing in this
   repo implements, configures, or benchmarks it. An outline that presents it
   as validated is a failed draft.
3. Keep proven and proposed material visually separated in the outline so a
   reviewer can see the ratio at a glance.
4. The five questions under "Questions to answer before writing starts" are
   blocking and are not yours to answer. Put them to the human first. If they
   decline to answer, state the assumption you are proceeding under at the top
   of the outline rather than burying it.

---

## The concept

Financial services customers (banks, insurers, distributors) receive documents
and structured data from dozens of source systems in inconsistent formats.
Today, ingestion and the AI applications built on top of those documents are
handled by per-source ETL scripts or manually.

The proposed example use case:

1. Airbyte uses certified connectors for Google Drive, SharePoint, PostgreSQL,
   and S3 to sync financial documents (invoices, contracts, regulatory docs)
   and structured transaction data into OpenShift AI on a schedule.
2. Post-ingestion, the corpus goes into AutoRAG, which automatically evaluates
   chunking strategies, embedding models, and retrieval configurations to find
   the optimal RAG pipeline for that specific corpus -- replacing manual tuning.

The natural two-part framing: the first half is an *integration* problem, the
second half is a *search-quality* problem. Teams usually only staff one of them.

---

## Questions to answer before writing starts

These are blocking. Each one changes the structure of the post, not just the
wording, so answering them after a draft exists means rewriting it. Suggested
owners in brackets.

1. **Is this a validation writeup with a forward-looking section, or a
   reference architecture piece that happens to cite a validation?**
   [post owner]
   This sets the ratio of proven to proposed material. The repo supports the
   first comfortably and the second only with heavy labeling.

2. **Will anyone close the gaps before publication?** [validation /
   engineering]
   Specifically: run the Google Drive, SharePoint, and S3 connectors; run an
   AutoRAG sweep; test scheduled sync; use a corpus that actually contains
   invoices, contracts, or regulatory documents. If yes, most of the post
   becomes provable and the writer should wait for results. If no, every one
   of those needs explicit "proposed" framing throughout.

3. **Which AutoRAG implementation, and how does it run on OpenShift AI?**
   [concept owner]
   Nothing in this repo names, configures, or benchmarks AutoRAG. Without an
   answer the section can only be written at hand-waving altitude, which will
   be obvious next to the hard numbers in the ingestion section.

4. **Has partner comms signed off on naming the HIGH-severity Airbyte bug
   publicly, and does Airbyte have an upstream fix in flight?** [partner comms
   / Airbyte relationship owner]
   Determines whether the bug is a credibility-building section, a footnote,
   or cut entirely. Also affects whether the post can recommend this pattern
   for production at all.

5. **Audience, venue, length, byline, and voice.** [post owner]
   Not in this brief. An AI agent will silently invent all five, and they
   drive the outline more than anything else here.

### Resolve while drafting -- not blocking

- **Redaction.** The repo is full of internal specifics: the cluster hostname
  `ai-dev02.kni.syseng.devcluster.openshift.com` appears throughout, including
  in the Route URL and demo script, and `examples/rag-pipeline/notebook.py`
  carries seed credentials (`airbyte_test` / `testpass123`). The five UI
  screenshots in `demo/screenshots/` should be checked for the same before
  reuse as figures.
- Whether to state the exact versions (OCP 4.21.16, RHOAI 3.4.1, Airbyte
  2.1.1) given they will age, or keep it to major versions.
- Whether the post mentions that this is the first of six planned data partner
  validations.
- Whether the two ASCII diagrams in `README.md` get redrawn as proper figures.

---

## What this repo is

A partner validation of Airbyte 2.1.1 on OpenShift 4.21.16 with Red Hat
OpenShift AI (RHOAI) 3.4.1. Verdict: **CONDITIONAL PASS**. Report date
2026-08-27. Full detail in [`README.md`](../README.md) and
[`reports/validation-report.md`](../reports/validation-report.md).

It is the first of six planned data partner validations.

---

## Evidence inventory -- what you can state as fact

Everything below was run on a real cluster and is backed by a file in this repo.

| Claim | Detail | Source |
|---|---|---|
| Deploys on OpenShift | Airbyte 2.1.1 via Helm, OCP 4.21.16 / K8s 1.34.7, 10 pods Running/Completed | `README.md` |
| Strictest SCC, no exceptions | All platform pods run under `restricted-v2` -- no custom SCCs, no root, no privilege escalation, `capabilities.drop: ["ALL"]`, `seccompProfile: RuntimeDefault` | `README.md`, `helm/openshift-values.yaml` |
| Coexists with RHOAI | 6/6 checks passed, 22 RHOAI pods healthy, zero conflicts, all 12 DataScienceCluster components unchanged | `reports/coexistence-check.txt` |
| No CRDs | Airbyte installs zero CRDs -- standard Deployments/Services/StatefulSets only, so zero CRD conflict risk | `reports/coexistence-check.txt` |
| Low footprint | ~205m CPU / ~2.2 GiB for all platform pods combined | `README.md` |
| End-to-end sync works | Job 6: 72 rows, 13,592 bytes, 3 tables, 3m 13s, Postgres source -> Postgres `airbyte_output` schema | `reports/sync-results.json` |
| API-driven | Source, destination, connection, and sync trigger all created through the Airbyte Public API | `scripts/04-configure-airbyte.sh` |
| RAG pipeline runs on the synced data | Fetch -> chunk (512 char / 64 overlap) -> embed (`all-MiniLM-L6-v2`, 384-dim) -> store JSONB -> cosine search, in an RHOAI Workbench | `examples/rag-pipeline/notebook.py` |
| Certification status | Not yet Red Hat certified. Preflight 7/10, chart-verifier 8/14. Failures are packaging/metadata, not functional | `reports/certification-results.json` |

### The architectural point worth leading with

Namespace isolation with a shared data plane. Airbyte runs in
`airbyte-validation` with its own service accounts and RBAC; RHOAI stays in
`redhat-ods-applications`. They share no CRDs, service accounts, or
cluster-scoped resources. They meet only at PostgreSQL, over in-cluster DNS
(`postgresql.airbyte-validation.svc.cluster.local`). No egress, no load
balancer, no API glue.

For a financial services audience this is the detail their security review will
ask about first.

### Two deployment gotchas worth a sidebar

Both will bite any reader who tries this:

1. **Two-step namespace creation.** `oc apply` of a namespace manifest carrying
   UID/GID annotations stops OpenShift from auto-populating the MCS annotation,
   and pods then fail SCC admission. Create the namespace first, annotate
   second. This is OpenShift behavior, not an Airbyte bug.
2. **API path change.** Airbyte V2 serves `/api/public/v1/`. The old `/api/v1/`
   returns 404. Any automation or monitoring needs updating.

---

## The honest part -- do not cut it from the post

Publishing this as a customer-facing use case without these caveats would
misrepresent the validation.

**Replication orchestrator resource bug (HIGH).** The orchestrator hardcodes
2 CPU / 2 Gi per container and ignores the Helm-configured values. A
4-container replication pod therefore requests 8 CPU and fails to schedule with
`Insufficient cpu` on any shared cluster. The evidence chain is clean and makes
a good concrete example: the ConfigMap `airbyte-airbyte-env` correctly contains
`REPLICATION_ORCHESTRATOR_CPU_REQUEST=250m`, the workload-launcher reads `250m`,
and the pod spec still says `2`. A manual pod-respec workaround exists and is
documented in `README.md` under Finding #1.

**Not Red Hat certified.** Preflight fails on missing `/licenses`, missing OCI
labels, and a non-UBI base image. Chart-verifier fails on missing
`values.schema.json`, missing `kubeVersion`, and uncertified images. None are
functional blockers. `RunAsNonRoot` passes, which is the check that actually
matters for OpenShift.

Before publishing, someone should confirm with partner comms whether naming a
HIGH-severity partner bug publicly is acceptable, and check whether Airbyte has
an upstream fix in flight.

---

## Gaps between the concept and the repo

The concept goes meaningfully beyond what was validated. Each of these is either
net-new work or needs explicit "proposed architecture" framing in the post.

1. **AutoRAG does not appear anywhere in this repo.** The existing example does
   fixed 512-character chunking with one hardcoded embedding model -- the
   literal opposite of automated tuning. This is the single biggest gap. Either
   run a real AutoRAG sweep or label the section clearly as proposed.
2. **Only PostgreSQL -> PostgreSQL was tested.** Google Drive, SharePoint, and
   S3 connectors were never exercised. S3 appears in the repo only as a
   *destination/storage* option for production hardening. The SCC and deployment
   results do generalize (all connector pods run as the same UID under
   `restricted-v2`), but per-connector resource behavior varies -- and given
   Finding #1, that caveat has teeth.
3. **No financial documents in the corpus.** The 17 seed documents in
   `data/seed.sql` are product docs, runbooks, and internal FAQs. Any claim
   about chunking or retrieval quality on invoices or contracts is currently
   unsupported.
4. **"On a schedule" was not tested.** Job 6 was triggered manually via the API.
   Scheduled sync is listed as a pattern, not a result.
5. **Embeddings are JSONB, not pgvector.** Search is a brute-force numpy dot
   product. Fine for 17 documents, not for a real corpus. The pgvector upgrade
   path (`vector(384)`, `<=>` cosine distance) is documented but not implemented.

### The useful bridge between what exists and what's proposed

The existing RAG example is a good setup for the AutoRAG section: every number
in it was a guess. 512 characters because it's round. MiniLM because it's fast.
That is exactly the manual tuning AutoRAG is meant to replace -- and a contract
corpus and an invoice corpus genuinely do have different optimal configs. A
compliance team also needs a *recorded reason* for the production config, not
"the ML engineer picked it in March."

---

## Source material

| Path | What's in it |
|---|---|
| `README.md` | Everything. Architecture, config reference, all 4 findings, certification detail, remediation roadmap |
| `reports/validation-report.md` | Structured validation report |
| `reports/coexistence-check.txt` | RHOAI coexistence results, 6/6 |
| `reports/sync-results.json` | E2E sync job metrics |
| `reports/certification-results.json` | Preflight + chart-verifier results |
| `demo/demo-script.md` | 15-min stakeholder walkthrough with talking points and an "If Asked" Q&A -- good source for narrative phrasing |
| `demo/dashboard.html` | PatternFly-styled summary dashboard |
| `demo/screenshots/` | 5 Airbyte UI screenshots (connections, sync details, timeline, sources, destinations) -- usable as post figures |
| `examples/rag-pipeline/` | The working RAG pipeline and its README |
| `helm/openshift-values.yaml` | The reusable artifact: OpenShift-compatible values overlay |
| `scripts/00`-`07` | Idempotent reproduction of the whole deployment and validation |
| `data/seed.sql` | 72 rows / 3 tables (documents, metadata, customers) |

Two diagrams already exist in ASCII and can be redrawn: the deployment
architecture and the Airbyte -> RHOAI data flow, both in `README.md`.
