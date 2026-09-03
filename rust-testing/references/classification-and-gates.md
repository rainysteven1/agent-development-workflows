# Classification And Gates

## Purpose

Use a qualitative testing pyramid while keeping three different questions separate:

1. What behavior boundary does the test cross?
2. What resources does the test consume?
3. Where does the test execute?

Collapsing these questions causes false rules such as "all integration tests are slow" or "all host
tests are unit tests."

## Behavior Boundary

| Boundary | Proves | Typical Rust shape |
| --- | --- | --- |
| `unit` | One function, type, or module invariant | `#[cfg(test)]` module or focused doctest |
| `component` | Multiple in-process units collaborate correctly | crate/module test with real collaborators or bounded fakes |
| `contract` | A schema, protocol, adapter, or public interface remains compatible | fixtures, golden vectors, consumer/provider contract |
| `integration` | A real boundary works, such as a database, filesystem, process, or service | `tests/`, Testcontainers, spawned process, real local service |
| `E2E` | A critical user or operator journey crosses the assembled system | CLI/API journey against a deployed or composed system |
| `recovery` | The system restores its invariant after interruption or partial failure | crash/restart, replay, failover, restore, compensation exercise |

The folder containing a test does not determine the boundary by itself. A file under `tests/` may
still be a small contract test; an inline test may start a real database and be an integration test.

## Resource Size

| Size | Resource envelope | Expected property |
| --- | --- | --- |
| `small` | One process; no real network or external service; bounded local I/O | fast, deterministic, highly parallelizable |
| `medium` | Multiple processes or local containers; bounded CPU, disk, and localhost I/O | isolated, explicit setup, seconds rather than minutes |
| `large` | Cluster, remote service, large corpus, long campaign, failover or recovery lab | explicitly scheduled, artifact-producing, operationally owned |

Use measured behavior to revise a size classification. Do not classify by name alone.

## Execution Location

| Location | Meaning |
| --- | --- |
| `host` | Developer or runner host without an external runtime boundary |
| `container` | Disposable local/containerized dependencies with controlled lifecycle |
| `CI-isolated` | Dedicated runner, namespace, VM, or trust domain created for the test |
| `staging` | Shared or dedicated pre-production environment with explicit credentials and cleanup |
| `production-safe-probe` | Read-only or strictly bounded probe designed and approved for production |

Location does not imply size. A small probe can run in production, and a large simulation can run on
a developer host.

## Technique Tags

Add any applicable tag without changing the boundary classification:

- `property`: generated examples test a semantic property.
- `fuzz`: coverage-guided inputs search for crashes or invariant violations.
- `mutation`: deliberate code changes measure whether assertions kill plausible defects.
- `concurrency`: more than one task or thread participates in the invariant.
- `fault-injection`: a dependency, process, clock, storage call, or lifecycle step fails deliberately.

## Qualitative Pyramid

Prefer a broad base of small tests, a narrower middle of medium boundary tests, and a small top of
large end-to-end and recovery tests. Do not set a universal percentage or test-count quota.

Break the default shape deliberately when the product is primarily an integration, when fidelity is
only available at a larger boundary, or when a safety/recovery claim cannot be decomposed. Record the
reason and keep the smallest lower-layer checks that still localize failures.

## Default Gate Matrix

| Change risk | Merge request | Scheduled or staging |
| --- | --- | --- |
| Pure/domain logic | affected small tests; component tests for public behavior | property, mutation, or fuzz campaign when useful |
| Async/concurrent logic | deterministic small tests plus affected component tests | Loom, scheduler stress, or multi-thread runtime checks |
| Parser/protocol/schema | examples plus contract fixtures | proptest/fuzz corpus and compatibility matrix |
| Database/service adapter | contract tests and bounded container integration | real-service compatibility or upgrade matrix |
| Durable lifecycle | transition and persistence tests | crash/restart/retry/partial-failure recovery matrix |
| Unsafe/FFI | focused tests and platform build matrix | Miri and sanitizer jobs where supported |
| Deployment/infrastructure | render/schema/contract checks | Kubernetes, Vault, registry, runner, failover, or recovery gate |

Change the matrix when measured cost or risk supports it. Keep the rationale alongside CI policy.

## Flaky Test Policy

Treat a flake as a concurrency, isolation, lifecycle, or environment defect until evidence proves
otherwise. Find the exact wait and earliest divergent event. Replace sleeps and assumed ordering with
observable synchronization.

Do not silently add retries. If temporary quarantine is unavoidable, record:

- stable test identity;
- owner;
- failure signature and impact;
- reason the test cannot block merges;
- issue or remediation path;
- expiry date and exit condition.

A retry may measure reproducibility after classification, but a pass-after-retry is not clean evidence.
