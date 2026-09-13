---
name: lean-delivery
description: Select the smallest correct, acceptance-complete implementation by preferring existing code, standard libraries, native platform capabilities, installed dependencies, and narrow local changes before new abstractions or dependencies. Use for implementation, bug fixes, refactors, dependency choices, architecture simplification, or reviews focused on over-engineering, YAGNI, boilerplate, speculative flexibility, or excessive scope. Do not use for independent adversarial review, pure evidence collection, Plane state transitions, or security review.
---

# Lean Delivery

Optimize the implementation path without changing the requested outcome. Applicable `AGENTS.md`, fixed acceptance criteria, and repository verification contracts remain authoritative.

Read and apply [the shared delivery contract](../dev-loop/references/delivery-contract.md)
when selecting scope. Evaluate an intermediate artifact by the final outcome and
its current supported consumers; do not optimize it into a general-purpose tool.
Use the contract's admission and cumulative detour checks for supporting work.

## Select the solution

After reading the task and tracing the affected flow, stop at the first option that satisfies the fixed acceptance criteria and direct effects:

1. Prove that no change is needed when the behavior already exists.
2. Reuse an existing repository helper, type, component, command, or pattern.
3. Use the standard library.
4. Use a native platform, browser, database, operating-system, or framework capability.
5. Use an already-installed dependency.
6. Write the smallest local implementation that works.

When two options are equally small, choose the one with fewer assumptions and clearer verification. Fix a shared root cause once after inspecting its callers instead of adding sibling patches.

## Execute the slice

1. State the user-visible outcome and narrow acceptance checks.
2. Inventory existing implementations and direct consumers before editing.
3. Implement only the selected slice; remove a superseded parallel path only after proving the replacement complete.
4. Run the repository-required targeted tests and a real usage check when applicable.
5. Inspect the final delta for speculative abstractions, dependencies, switches, compatibility layers, and duplicate behavior.
6. Report the change, verification evidence, and any unverified risk using the repository's required format.

## Preserve delivery integrity

- Do not replace an explicit requirement with an easier partial substitute.
- Do not simplify away required generated artifacts, migrations, documentation, observability, rollback behavior, tests, evidence, or planning updates.
- Do not weaken trust-boundary validation, authorization, security, accessibility, or data-loss prevention.
- Choose tests from the changed risk surface and repository contract; never impose a one-test cap.
- Do not add future-facing structure without a current acceptance criterion, second concrete consumer, or measured constraint.
- Record a real simplification ceiling as `Deferred` with the observable trigger and upgrade path; it is not a current blocker.
- Never invoke or influence an independent adversarial reviewer. Complexity-focused inspection under this skill is an ordinary, non-gate self-check and does not add a review round.

This workflow adapts the YAGNI and reuse-first decision ladder from DietrichGebert/ponytail (MIT) to an acceptance- and evidence-driven delivery harness.
