---
name: tdd
description: Implement or protect observable behavior with a risk-driven red-green-refactor loop at a stable seam. Use for test-first features, behavior changes, and regression tests; do not use for prose, generated artifacts, throwaway exploration, or changes with no meaningful executable behavior.
---

# Test-Driven Development

Build one observable behavior at a time and prove that its test can detect the
missing or broken behavior before implementation. `$dev-loop` owns delivery;
this skill owns the red-green-refactor feedback loop.

## Choose the behavior and seam

Start from an accepted requirement or one `AC-*` identifier. Identify the real
caller, public contract, risk, and narrowest test layer that can observe the
behavior: unit, component, contract, integration, end-to-end, or recovery.

Derive the seam from current code and repository conventions. Ask the user only
when choosing it changes a product or architecture contract. If the interface
itself is the problem, use `$codebase-design` before writing the test. Do not
create an adapter or abstraction solely to satisfy a mock.

## Run one vertical cycle

1. Write one focused test that expresses the behavior through the selected
   seam. Use an independently known expected value, not the implementation's
   own algorithm.
2. Run the narrow command and observe the expected failure. A syntax, fixture,
   setup, or unrelated failure is not red evidence; correct it until the test
   fails because the target behavior is absent or broken.
3. Implement the smallest production change that makes this test pass. Do not
   anticipate later cases or bundle unrelated refactoring.
4. Re-run the focused test, then the smallest impacted suite. Record both
   commands and results.
5. Refactor only while the tests remain green. Re-run the focused test after
   every behavior-preserving structural change.
6. Continue with the next independently meaningful behavior.

## Test quality

- Test externally visible results, contracts, and failure modes rather than
  private methods or internal call order.
- Prefer real code. Replace only slow, nondeterministic, destructive, or truly
  external dependencies, and assert the public result rather than mock trivia.
- Keep fixtures minimal and make the test name describe one behavior.
- For asynchronous behavior, wait for the state or event under test with a
  bounded timeout and diagnostic failure. Use fixed sleeps only when elapsed
  time is itself the behavior, and document the timing invariant.
- Preserve a realistic failure path. A passing happy-path test alone does not
  cover validation, authorization, recovery, or concurrency risks named by the
  acceptance contract.

## Regression fixes and exceptions

For a bug fix, the red test must reproduce the user's exact minimized symptom
at a correct seam. If no such seam exists, record that architecture gap and
return to `$codebase-design`; a shallow test that cannot reproduce the causal
chain creates false confidence.

Test-first may be inapplicable to generated output, declarative configuration,
throwaway prototypes, or behavior that only external hardware or a human can
observe. Label the exception, name the alternative verification, and preserve
it in the task evidence. An exception changes the feedback mechanism, not the
acceptance requirement.

Return the behavior or `AC-*` ID, selected seam and test layer, red command and
expected failure, green command and result, impacted-suite result, and any
explicit exception. Never claim TDD when the test was not observed failing for
the intended reason.
