# Async And Concurrency

## Separate The Claims

Async and concurrent tests can prove different things:

- functional behavior of an async API;
- timeout and cancellation semantics;
- task ownership and shutdown;
- bounded parallelism and backpressure;
- thread safety and atomic invariants;
- correctness across possible interleavings.

Name the claim before choosing a runtime or tool. A `#[tokio::test]` does not by itself prove a race is
impossible, and a Loom model does not prove behavior against a real database or network.

## Test Tokio Behavior Deterministically

Use the runtime flavor required by the behavior. Prefer current-thread execution for ordinary async
logic when multi-thread scheduling is not part of the claim. Use a multi-thread runtime only when the
code or invariant requires it.

For timer-driven behavior, enable Tokio's `test-util` support and use paused time when compatible:

```rust
#[tokio::test(start_paused = true)]
async fn lease_expires_at_deadline() {
    let lease = start_lease(Duration::from_secs(30));
    tokio::time::advance(Duration::from_secs(30)).await;
    assert_eq!(lease.state().await, LeaseState::Expired);
}
```

Do not assume paused time controls external I/O or all scheduler interleavings. Use an injected clock
when domain logic should not depend directly on Tokio.

## Prove Cancellation And Shutdown

For spawned work, test:

- who owns the task or join handle;
- what happens when the caller future is dropped;
- whether cancellation leaves partial state;
- whether child tasks drain or leak;
- whether shutdown waits for committed work and rejects new work;
- whether timeout means known failure or unknown external outcome.

Drive tests with channels, barriers, notifications, cancellation tokens, or a controlled fake
dependency. Avoid `sleep` followed by an assertion.

## Prove Parallelism With Observation

To claim that work overlaps, record or expose a stable observation:

- start and finish timestamps from an injected monotonic clock;
- a barrier showing two tasks reached an active section;
- a maximum in-flight counter;
- a trace or event sequence with stable task identities;
- equivalence between concurrent output and a sequential model.

Mocked spawn calls, a semaphore declaration, or a CI matrix only proves configuration, not overlap.

## Use Loom For Interleaving Risk

Use Loom when correctness depends on `Arc`, atomics, mutexes, channels, or custom synchronization and
the relevant state can be reduced to a small model. Route synchronization types through a test
configuration so the same algorithm can run with Loom primitives.

Keep the model small:

- minimize threads, operations, and state;
- assert a semantic invariant after all modeled operations;
- avoid unbounded loops and progress assumptions such as spin waiting;
- control preemption and branch bounds only after understanding why the state space grows;
- keep a regression for every discovered interleaving.

Do not claim Loom explored code that still uses uninstrumented `std` synchronization internally. Do
not use Loom as a replacement for real-runtime cancellation, I/O, or integration tests.

## Stress Only After Deterministic Checks

Repeated nextest or cargo runs can expose residual scheduling and isolation defects, but repetition is
not a proof. Preserve the seed, command, test identity, concurrency level, and failure artifact. If a
stress run flakes, diagnose the earliest divergent event before adding retries or longer waits.

## Review Checklist

- Does the test assert an externally meaningful concurrency invariant?
- Is time controlled or observed without a race window?
- Are task ownership, cancellation, and shutdown explicit?
- Does every bounded wait surface useful state on timeout?
- Is Loom instrumenting every relevant synchronization primitive?
- Does a real-runtime test cover assumptions omitted by the model?
