# Advanced Rust Test Gates

## Use Nextest As A Runner, Not A Quality Policy

Adopt nextest for process-per-test isolation, filtering, profiles, partitioning, slow-test reporting,
and CI output when the suite benefits. Keep its configuration checked in and pin the installation in
CI according to repository policy.

Before replacing a command, verify:

- doctests remain covered by an explicit gate;
- tests do not depend on same-process globals or working-directory assumptions;
- setup scripts and per-test overrides are represented;
- profile retries do not turn flakes into passes;
- local and CI commands select the same intended tests.

Use stress or repeated execution to reproduce nondeterminism, not to certify its absence.

## Use Miri For Relevant Undefined-Behavior Risk

Run Miri for owned unsafe code, raw pointers, custom allocation, FFI-adjacent logic that Miri supports,
and minimized regressions involving aliasing or concurrency. Pin a compatible nightly when
reproducibility matters.

Miri is an interpreter with unsupported platform and FFI behavior; scope tests accordingly. A safe
crate may still call unsafe dependencies, so decide based on the owned risk and reachable code rather
than a simple source grep. Miri passing does not prove all unsafe code sound.

## Use Mutation Testing To Test The Tests

Run cargo-mutants on logic where plausible code changes should be killed by assertions. Start with a
focused package or module and an explicit time budget. Classify survivors:

- missing assertion or missing test;
- equivalent mutation;
- unreachable or dead code;
- timeout or harness instability;
- intentionally tolerated behavior.

Do not chase a universal mutation score. Fix high-risk survivors first and record exclusions with
rationale. Keep mutation jobs scheduled or opt-in when their cost is unsuitable for merge requests.

## Use Coverage As An Observation Map

Use cargo-llvm-cov or the repository's established tool to locate unexecuted branches and modules.
Measure the relevant feature, target, and workspace configuration. Exclude generated or unreachable
code only with a visible reason.

Coverage does not measure assertion strength, input diversity, recovery behavior, or concurrency
interleavings. Do not set one percentage for pure domain code, adapters, generated bindings, and
operational integration code. A local threshold is valid only when tied to risk and maintained by the
owning project.

## Keep CI Gates Layered

A typical progression is:

1. format, compile, and static checks;
2. affected small tests and MR-safe contract tests;
3. workspace tests, including doctests;
4. bounded container integration;
5. scheduled property, fuzz, mutation, Miri, and stress jobs;
6. explicit staging, end-to-end, and recovery gates.

Select layers based on changed paths and dependency impact, but do not let path filters skip shared
contracts or downstream consumers. Preserve a manual or scheduled full gate that detects mistakes in
impact analysis.

## Diagnose Flakes Before Retry

Collect the first failing seed, event, process exit, resource state, and waiting layer. Check hidden
global state, port conflicts, environment mutation, test-order coupling, leaked tasks/processes,
unbounded scheduling, real-time assumptions, and external readiness.

Only configure retry after classifying a failure as transient and measuring recovery behavior. Keep a
retry-visible result from being reported as a clean pass.
