# Red Hat Certification Status

Airbyte is **not yet Red Hat certified**. Both preflight (container image) and chart-verifier (Helm chart) fail with pre-certification gaps. These are metadata and packaging issues, not functional blockers.

---

## Preflight -- Container Image (7 pass / 3 fail)

Tool: `openshift-preflight 1.21.0` against `docker.io/airbyte/server:2.1.1`

| Check | Result | Detail |
|-------|--------|--------|
| HasUniqueTag | PASS | Tag `2.1.1` (not `latest`) |
| LayerCountAcceptable | PASS | Under 40 layers |
| HasNoProhibitedPackages | PASS | No RHEL kernel packages |
| HasNoProhibitedLabels | PASS | No Red Hat trademark violations |
| RunAsNonRoot | PASS | Runs as `airbyte:airbyte` |
| HasModifiedFiles | PASS | No modified RPM files |
| HasProhibitedContainerName | PASS | No trademark violations |
| HasLicense | **FAIL** | No `/licenses` directory in image |
| HasRequiredLabel | **FAIL** | Missing: `name`, `vendor`, `version`, `release`, `summary`, `description`, `maintainer` |
| BasedOnUbi | **FAIL** | Image not based on UBI/RHHI |

The `RunAsNonRoot` pass is the most critical result for OpenShift compatibility.

---

## Chart-Verifier -- Helm Chart (8 pass / 5 fail / 1 skipped)

Tool: `chart-verifier 1.16.0` against `airbyte-2.1.1.tgz`, profile `partner v1.3`

| Check | Result | Detail |
|-------|--------|--------|
| contains-test | PASS | Test files present |
| has-notes | PASS | NOTES.txt present |
| not-contains-crds | PASS | No CRDs |
| has-readme | PASS | README present |
| helm-lint | PASS | Lint clean |
| contains-values | PASS | values.yaml present |
| is-helm-v3 | PASS | API version v2 |
| not-contain-csi-objects | PASS | No CSI objects |
| contains-values-schema | **FAIL** | No `values.schema.json` |
| has-kubeversion | **FAIL** | `kubeVersion` not in Chart.yaml |
| images-are-certified | **FAIL** | 0 of 11 images Red Hat certified |
| chart-testing | **FAIL** | Requires live cluster (ran in podman) |
| required-annotations-present | **FAIL** | Missing `charts.openshift.io/name` |
| signature-is-valid | SKIPPED | Chart unsigned |

---

## What Needs to Happen for Certification

**Container images:**

1. Rebase all Dockerfiles on `registry.access.redhat.com/ubi9/ubi-minimal:latest` (or `ubi9/openjdk-21-runtime` for JVM services)
2. Add a `/licenses` directory containing the Apache 2.0 license text and third-party notices
3. Add required OCI labels to each Dockerfile:

```dockerfile
LABEL name="airbyte-server" \
      vendor="Airbyte" \
      version="2.1.1" \
      release="1" \
      summary="Airbyte data integration server" \
      description="Airbyte server component for data integration pipelines" \
      maintainer="Airbyte <support@airbyte.io>" \
      io.k8s.display-name="Airbyte Server" \
      io.openshift.tags="airbyte,data-integration,etl"
```

4. Submit images to the Red Hat Connect portal for certification scanning
5. Publish certified images to `registry.connect.redhat.com`

**Helm chart:**

1. Generate and include `values.schema.json`
2. Add `kubeVersion` to Chart.yaml:

```yaml
kubeVersion: ">=1.26.0-0"
```

3. Add OpenShift annotation to Chart.yaml:

```yaml
annotations:
  charts.openshift.io/name: airbyte
```

4. Sign the chart with a GPG key and publish the provenance file alongside the `.tgz`

Full results: [`reports/certification-results.json`](../reports/certification-results.json)
