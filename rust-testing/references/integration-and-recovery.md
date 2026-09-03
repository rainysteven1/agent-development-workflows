# Integration And Recovery

## Test A Real Boundary Only When It Matters

Use an integration test when the claim depends on a real database engine, filesystem, process,
protocol stack, object store, broker, service, or deployment platform. Keep pure decision logic below
that boundary covered by small tests so integration failures remain diagnosable.

Use Testcontainers or an equivalent disposable runtime when it provides the required fidelity and the
repository can guarantee a compatible container engine. Do not add Testcontainers to a project that
already has a simpler authoritative harness without a measured benefit.

## Own The Environment

- Pin images by version or digest according to repository supply-chain policy.
- Wait for a semantic readiness condition, not a fixed sleep.
- Allocate unique databases, schemas, buckets, ports, namespaces, and ownership IDs.
- Keep credentials test-scoped and never print secrets.
- Capture service logs and state needed to diagnose a failure.
- Tear down by exact identity and surface cleanup failures.
- Bound setup and calls with diagnostic timeouts that report the blocked layer.

Use migrations and production-compatible configuration when schema or startup compatibility is part
of the claim. Do not silently replace the production engine with SQLite or an in-memory fake when
engine behavior matters.

## Validate Before Mutation

For a batch or plan/apply workflow, test that all inputs, permissions, revisions, dependencies, and
ownership identities are validated before the first external mutation. Invalid input must leave zero
partial mutation when the contract promises atomic validation.

Assert durable state and external state, not only client calls. Re-observe after mutation before
claiming convergence.

## Exercise Durable Lifecycles

When code owns a long-lived resource or workflow, derive the applicable matrix:

| Case | Evidence |
| --- | --- |
| create | new resource has stable identity and intended invariant |
| update | changed fields converge without replacing unrelated state |
| rename | identity and ownership remain unambiguous |
| delete | exact owned resource is removed; survivors are re-read |
| retry | idempotent replay does not duplicate effects |
| restart | durable state reconstructs without process-local truth |
| partial failure | committed and uncommitted effects are classified and recoverable |

Add duplicate callback, permission loss, drift, cancellation, timeout/unknown, compensation failure,
and concurrent ownership conflict when the contract permits them.

## Inject Failures At Commit Boundaries

Place failpoints before a call, after a remote success but before local persistence, between dependent
actions, during status publication, and during compensation. Each failpoint should have a named
expected recovery path.

Distinguish:

- known failure: no external effect occurred;
- known success: the effect is durably observed;
- timeout/unknown: the effect may have occurred and requires re-observation;
- partial failure: some effects committed and others did not;
- compensation failure: recovery itself requires durable operator evidence.

Never replay an unknown non-idempotent operation blindly.

## Use Staging For Operational Claims

Run Kubernetes, Vault, registry, runner, deployment, failover, and backup/restore tests in an explicit
staging or isolated environment when a local container cannot prove the claim. Resolve the exact
target inventory before destructive work and re-read both surviving and removed resources afterward.

Record revisions, resource identities, environment, timestamps, attempts, observations, recovery
actions, and artifact locations without exposing credentials.
