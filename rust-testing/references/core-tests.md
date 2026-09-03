# Core Rust Tests

## Start From A Failure Hypothesis

Before writing a test, name:

- the invariant the production code must preserve;
- the smallest input or event sequence that could violate it;
- the observable result that would distinguish the defect;
- the likely false-green assertion.

Prefer a counterexample that would fail under a plausible mutation, not a collection of arbitrary
edge values. For bug fixes, run the counterexample against the broken behavior before implementing the
fix whenever practical.

## Choose Test Placement By Access Need

- Put focused tests in `#[cfg(test)]` modules when private helpers are part of a useful module-level
  invariant.
- Put public API and cross-crate tests under `tests/` when they should compile as external consumers.
- Use doctests for short public examples that must remain compilable and behaviorally true.
- Split large test modules only when navigation or compilation boundaries improve. Do not impose one
  file layout on every crate.

Remember that nextest does not make doctest verification disappear. Preserve an explicit doctest or
`cargo test` gate when adopting a different runner.

## Assert Semantic Outcomes

Assert the full meaningful result: value, error variant, durable state, side effect, emitted evidence,
or absence of forbidden mutation. Avoid assertions that only prove a call returned `Ok`.

Prefer stable semantic comparisons over formatting details. Exact snapshots are appropriate for a
deliberately stable user-facing or serialized contract, but review snapshot diffs and normalize
volatile IDs, timestamps, paths, and map ordering.

Use the repository's assertion style. Add `pretty_assertions`, `insta`, or another dependency only when
the diagnostic value exceeds dependency and maintenance cost.

## Build Fixtures With Ownership And Cleanup

- Give tests independent state by default. Share state only when shared caches,
  contention, process globals, or persistence across phases are the behavior
  under test; scope, serialize, and clean up that state explicitly.
- Use RAII guards for temporary directories, servers, processes, ports, and transactions.
- Avoid process-global environment mutation in parallel tests. Prefer dependency injection; otherwise
  serialize and restore the state safely.
- Generate unique stable identities for shared external resources and delete by exact ownership.
- Keep fixture builders explicit enough that the scenario is readable.
- Verify teardown failures rather than swallowing them when leaked state can affect later tests.

Use real collaborators inside a component when they are deterministic and cheap. Prefer a fake over a
mock for stateful behavior. Use interaction mocks only when the interaction itself is the contract or
the real dependency cannot be controlled.

## Cover The Behavior Matrix

Derive cases from the contract. Common candidates include:

- valid, boundary, malformed, empty, duplicate, and oversized input;
- permission denied and ownership mismatch;
- version/schema compatibility and unknown fields;
- idempotent replay and duplicate callbacks;
- cancellation before, during, and after an external effect;
- timeout with known failure versus timeout with unknown remote outcome;
- rename/delete identity safety;
- restart, partial persistence, and compensation failure.

Do not apply every row mechanically. Mark a row not applicable with a reason when reviewing a
high-risk lifecycle.

## Keep Tests Deterministic

- Inject or pause time instead of waiting for wall-clock time.
- Seed randomness and print the seed on failure.
- Sort only when ordering is not part of the contract; otherwise assert the required order.
- Avoid shared mutable globals and fixed ports.
- Bound waits with a diagnostic timeout, but do not increase the timeout before locating the blocked
  layer and checking progress.
- Make a failed test name identify the violated behavior, not merely the function under test.

## Run Narrow To Broad

Discover and reuse checked-in commands. Typical shapes, only when compatible with the repository:

```bash
cargo test -p crate_name test_name --all-features --locked
cargo test -p crate_name --test contract_name --all-features --locked
cargo test --workspace --all-features --locked
cargo test --doc --workspace --all-features --locked
```

Do not add flags the manifest or lock policy cannot support. Report the exact command actually run.
