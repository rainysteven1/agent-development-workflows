---
name: rust-testing
description: Design, write, review, and verify risk-driven Rust tests across unit, component, contract, integration, end-to-end, and recovery boundaries. Use for Cargo test strategy, TDD and regression tests, Tokio async or concurrency tests, proptest, Loom, cargo-fuzz, Testcontainers, Miri, cargo-mutants, cargo-llvm-cov, nextest, flaky-test diagnosis, and Rust CI test gates.
---

# Rust Testing

## Objective

Turn each Rust behavior change or defect into durable, reproducible evidence. Prefer the smallest
test that faithfully exercises the risk, then add broader tests only for boundaries that the smaller
test cannot prove.

Treat repository instructions, executable code, existing tests, and CI as the local authority. This
skill supplies a decision system; it does not replace a repository's explicit test contract.

## Establish The Baseline

Before changing tests or behavior:

1. Read the closest `AGENTS.md` or equivalent project instructions.
2. Inspect `Cargo.toml`, the workspace graph, toolchain files, checked-in test configuration, and CI.
3. Find the narrowest existing test command and the merge-gating command.
4. Capture the task-start Git state and focused diff for relevant files.
5. State the behavior, invariant, smallest counterexample, and acceptance checks.

Run `scripts/audit_rust_tests.py <repo>` when the Rust test surface is unclear. Treat its output as
an inventory, not a quality verdict.

## Classify Every Test

Assign every new or materially changed test three independent dimensions. Record them in test
metadata, a test plan, CI configuration, or the verification report; do not require an inline comment
unless the repository does.

| Dimension | Values |
| --- | --- |
| Behavior boundary | `unit`, `component`, `contract`, `integration`, `E2E`, `recovery` |
| Resource size | `small`, `medium`, `large` |
| Execution location | `host`, `container`, `CI-isolated`, `staging`, `production-safe-probe` |

Use `property`, `fuzz`, `mutation`, `concurrency`, and `fault-injection` as technique tags. Never turn
them into competing test layers. Read `references/classification-and-gates.md` before designing a
suite, changing CI gates, or discussing the test pyramid.

## Follow The Test Loop

1. **Form a failure hypothesis.** Name what could break, the violated invariant, and the observation
   that distinguishes correct behavior from a false green.
2. **Choose the lowest faithful boundary.** Start with a small host test when it can prove the
   behavior. Cross a process, persistence, network, or deployment boundary only when that boundary
   is part of the claim.
3. **Prove the test is live.** For a bug, run the reproduction against the broken behavior. For new
   behavior, make the test fail for the expected missing-behavior reason when practical. Do not use
   compilation failure or an unrelated panic as RED evidence.
4. **Implement the smallest passing slice.** Avoid test-only production branches and broad
   refactors unless the acceptance criteria require them.
5. **Run targeted verification.** Run the narrowest relevant test first. Include one meaningful edge
   or failure case for a medium-risk change.
6. **Exercise realistic usage.** Run the public API, CLI, service boundary, persisted restart, or
   other caller path represented by the change.
7. **Run the affected gate.** Expand to workspace or CI-equivalent checks according to dependency
   surface and risk, not ritual.
8. **Report evidence.** Include commands, environment, result, dimensions, technique tags, and any
   skipped checks with reasons.

## Route To Focused Guidance

Read only the references needed for the current risk:

| Need | Read |
| --- | --- |
| Test pyramid, three dimensions, MR and staging gates | `references/classification-and-gates.md` |
| Unit, component, contract, fixtures, assertions, doctests | `references/core-tests.md` |
| Tokio, cancellation, time, scheduling, threads, Loom | `references/async-and-concurrency.md` |
| Proptest, state models, cargo-fuzz, corpora and regressions | `references/property-and-fuzz.md` |
| Databases, containers, external services, restart and recovery | `references/integration-and-recovery.md` |
| nextest, Miri, mutation, coverage, CI and flaky tests | `references/advanced-gates.md` |
| Upstream evidence and tool limitations | `references/sources.md` |

Combine references when the behavior crosses concerns. For example, a concurrent durable state
machine normally needs core, async/concurrency, and integration/recovery guidance.

## Enforce The Qualitative Pyramid

Maintain many fast, deterministic small tests; fewer medium tests across important boundaries; and a
small set of large end-to-end or recovery tests for critical journeys and operational invariants.

Do not prescribe a universal numeric ratio. Do not optimize test counts. Optimize risk coverage,
feedback speed, failure localization, fidelity, and maintenance cost. A system whose product is an
integration may intentionally carry more medium or large tests; record why.

## Apply Risk-Driven Gates

- Run all affected small tests on merge requests. Run affected medium and
  contract tests there only when their resource size and execution location are
  MR-safe; route large or staging-bound contract evidence to its explicit gate.
- Run real databases, object stores, brokers, and similar dependencies as container integration tests
  when a fake cannot prove the contract.
- Put real Kubernetes, Vault, Harbor, Runner, deployment, and recovery exercises behind explicit
  staging gates when those systems are in scope.
- Cover `create`, `update`, `rename`, `delete`, `retry`, `restart`, and `partial failure` for code that
  owns a durable lifecycle. Add permission, drift, cancellation, timeout/unknown, and compensation
  cases when the contract permits them.
- Prove concurrency with an observable invariant such as timestamps, barriers, ownership, or model
  outcomes. Configuration shape or mocked call order is not execution evidence.
- Diagnose flaky tests at the waiting layer. Do not make retries the default fix. Quarantine only with
  an owner, reason, impact, expiry, and exit condition.

## Avoid False Standards

- Do not force a coverage percentage across repositories or package types. Use coverage to find
  unobserved risk, then inspect assertion strength and add risk-derived tests.
- Do not require `pretty_assertions`, `mockall`, `rstest`, snapshots, sibling test files, or a fixed
  number of cases. Adopt a dependency only when it improves the local test contract.
- Do not replace `cargo test` blindly with nextest. Preserve doctest coverage and check runner
  compatibility.
- Do not run Loom, Miri, fuzzing, mutation testing, or Testcontainers everywhere. Apply each tool only
  where its fault model can invalidate a relevant assumption.
- Do not use wall-clock sleeps as synchronization in deterministic tests. Use events, barriers,
  injected clocks, paused Tokio time, or bounded polling of an observable condition.
- Do not assert private call order when an externally visible state or output can prove the behavior.
- Do not accept `is_ok()`, `is_err()`, or "did not panic" alone when the returned state, error variant,
  side effect, or invariant can be checked.

## Exit With Evidence

Before declaring the task complete, report:

- the behavior and failure hypothesis;
- each test's three dimensions and technique tags;
- RED evidence for a defect or new behavior when feasible;
- targeted, realistic-usage, and broader commands with results;
- toolchain and relevant execution environment;
- remaining untested risk and why it remains;
- flaky-test quarantine metadata, if any.

For changes to this skill, run `scripts/validate_skill.py` and the system `quick_validate.py`, then
forward-test at least one ordinary Rust change and one async, persistence, or concurrency scenario.
