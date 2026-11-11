# Airbyte platform-check evidence

Run date: 2026-11-10 (UTC). Cluster: ai-dev02; namespace:
`airbyte-validation`. OpenShift server: 4.21.16. RHOAI: 3.5.2. Airbyte:
2.1.1, Helm revision 14.

These are runtime observations for Appendix A. They are separate from the
functional four-source sync and RAG evidence.

Owner disposition: Ramesh advised documenting the observed Airbyte chart and
deployment limitations and discussing them with the Airbyte partner. No local
remediation is required for this reference validation.

## Status

- **P1 — Qualified limitation.** The Helm release uses external AWS S3 for
  Airbyte state/workload storage, with `global.storage.type: s3` and
  `minio.enabled: false`. However, `postgresql.enabled: true` and
  `airbyte-db-0` are still present. This chart limitation is documented for
  partner review.
- **P2 — Qualified chart exception.** Airbyte core pods run under
  `restricted-v2` with `runAsUser: 1000` and pod `fsGroup: 1000`; runtime
  pods report `runAsNonRoot: true`. The fixed user/group settings are a
  documented chart limitation; no local remediation is required for this
  reference validation.
- **P3 — Qualified pass.** Legal, compliance, S3, and PostgreSQL
  source-check pods were observed under `restricted-v2` with service account
  `airbyte-admin`, UID 1000, and `runAsNonRoot=true`. Schema discovery also
  succeeded for all four sources through the Airbyte API. Replication-pod
  SCC/UID evidence is now recorded for all four sources. The financial sync
  completed successfully; controlled legal, compliance, and PostgreSQL probe
  jobs were Pending because eight nodes reported insufficient CPU and were
  canceled intentionally. The scheduled legal, compliance, and PostgreSQL
  jobs remained successful. The CPU scheduling exception is recorded
  separately and is not an SCC failure.
- **P4 — Qualified RBAC limitation.** `airbyte-admin-role` is project-scoped,
  but its single rule uses `apiGroups: ["*"]` and grants create, delete, get,
  list, patch, update, and watch over configmaps, endpoints, jobs, pods, pod
  attach/exec/log, and secrets. It is bound to the `airbyte-admin` service
  account through `airbyte-admin-binding`. This broad role is documented for
  platform and partner review; no local narrowing is required for this
  reference validation.
- **P5 — Qualified storage limitation.** No `hostPath` volume is used and the
  approved AWS S3 bucket is reachable. The bundled Airbyte PostgreSQL database
  remains, and a historical `airbyte-minio-0` pod/PVC is still present, so all
  chart state is not externalized. This is documented for partner review.
- **P6 — Pass observed.** Airbyte downloaded its connector catalog, pulled
  connector images, reached the Google Drive API, and completed the four
  production syncs.
- **P7 — Qualified security finding.** The Airbyte Route uses TLS edge
  termination and the web UI requires login. The unauthenticated Public API
  route returned HTTP 200 during validation, including a connection request.
  This behavior is documented for platform and partner review; no local
  remediation is required for this reference validation.
- **P8 — Deferred by agreement.** The current dataset is intentionally
  limited. ResourceQuota, LimitRange, and larger-load behavior will be tested
  later with a larger corpus and approved capacity target.
- **P9 — Pass.** After an additional untainted CPU worker became available,
  the Airbyte workload-launcher was restarted during controlled legal job 52.
  The replacement launcher became Ready and the sync completed successfully
  with 144 files and 45,693,114 bytes. A same-version Helm upgrade completed
  as revision 14, and post-upgrade legal job 53 also succeeded with 144 files
  and 45,693,114 bytes.

## Runtime inventory

The effective Helm values show:

- `global.storage.type: s3`
- S3 state/workload bucket: `ai-dev02-bucket01-data`
- `minio.enabled: false`
- `postgresql.enabled: true`
- file-transfer request/limit: 5 GiB

## P8 quota planning

The namespace currently has no `ResourceQuota` or `LimitRange`. The four
production schedules are staggered six hours apart, but retries and manual
runs can overlap. Airbyte file-transfer workloads are configured with a 5 GiB
ephemeral-storage request and limit per sync pod. The current namespace also
contains the Airbyte services, Milvus, PostgreSQL, and the Ray RAG workers, so
their requests must be included if the quota applies to the whole namespace.

Before applying a quota, stakeholders must confirm the maximum number of
concurrent Airbyte syncs, whether RAG workloads share this quota, and the
LimitRange defaults. The minimum ephemeral-storage request for N concurrent
file-transfer syncs is 5 GiB multiplied by N, with additional headroom for
temporary files and checks/discoveries. No quota manifest is applied by this
validation until those values are confirmed.

## P3 source evidence

| Source | Check pod result | Discovery result |
| --- | --- | --- |
| Google Drive legal | Succeeded; `restricted-v2`; UID 1000; non-root | Succeeded; job `f248eeda-a761-4839-ad07-88bb2813af50` |
| Google Drive compliance | Succeeded; `restricted-v2`; UID 1000; non-root | Succeeded; job `77871da6-6753-4d98-a81d-10d20caf0cb1` |
| Financial S3 | Succeeded; `restricted-v2`; UID 1000; non-root | Succeeded; job `ee481d3f-202e-49a0-9af0-6c87893ac65c` |
| SEC PostgreSQL | Succeeded; `restricted-v2`; UID 1000; non-root | Succeeded; job `44429203-3789-4873-bdf9-64a4e76daad0` |

The financial replication pod from the complete 32-file sync was also
observed under `restricted-v2` with the configured non-root service account
and 2 GiB container limit. The other three production replication-pod
observations were captured during controlled probes: legal job 47, compliance
job 48, and PostgreSQL job 49. Each used `restricted-v2`, service account
`airbyte-admin`, UID 1000, non-root containers, and 512 MiB requests/2 GiB
limits per orchestrator, source, and destination container. Those probes were
canceled after the scheduler reported insufficient CPU; they were not part of
the unattended S2 window.

The namespace has no `hostPath` volumes in its Deployment, StatefulSet, or
DaemonSet workloads. The bound PVCs include Airbyte database storage, a
MinIO PVC, Milvus storage, Milvus etcd storage, and the seeded PostgreSQL
storage.

## P4 RBAC review

The direct Airbyte permission surface is the namespaced `airbyte-admin-role`.
The role is broad, using `apiGroups: ["*"]` and allowing pod exec/attach/log
and secret access. This is recorded as a qualified RBAC limitation for
platform and partner review; no local narrowing was required for this
reference validation. The effective cluster-level permissions visible in
`oc auth can-i` are also present on the namespace `default` service account,
so they are not attributed to the Airbyte Role in this finding.

## Next platform actions

1. Discuss the P1, P2, P4, P5, and P7 limitations with the Airbyte partner;
   no local remediation is required for this reference validation.
2. Confirm quota values with stakeholders before applying a P8
   `ResourceQuota`/`LimitRange`.
