---
name: codebase-design
description: Design or evaluate module responsibilities, interfaces, ownership boundaries, and testing seams. Use for architecture, cross-caller refactors, testability problems, or unclear interface placement; do not use for routine local edits.
---

# Codebase Design

Choose a design that gives callers leverage, keeps related change local, and
exposes behavior through a stable testing seam. This skill supplies design
judgement; `$repo-evidence` supplies repository facts and `$lean-delivery`
controls implementation scope.

## Design lens

Use these concepts internally while preserving the repository's established
domain language in user-facing output:

- **Module**: a unit with an interface and implementation at any scale.
- **Interface**: everything callers must know, including invariants, ordering,
  errors, configuration, and performance constraints.
- **Seam**: a location where behavior can vary or be observed without editing
  the caller.
- **Adapter**: an implementation that occupies a seam.
- **Depth**: useful behavior hidden behind a smaller caller-facing contract.
- **Leverage and locality**: capability reused by callers and change contained
  for maintainers.

## Evaluate the boundary

1. Trace current behavior, owners, callers, data flow, and failure paths.
2. Name the responsibility that changes together and the authority that should
   own it.
3. Compare the current and proposed interfaces by required caller knowledge,
   coupling, failure visibility, testability, and migration cost.
4. Consider more than one interface only when a real tradeoff exists. Prefer
   the smallest design that satisfies current acceptance criteria.
5. State the chosen seam, invariants, adapter responsibilities, and observable
   test surface.

Apply heuristics with context:

- A pass-through layer that removes no complexity is probably shallow.
- One adapter is evidence against speculative abstraction, not a prohibition;
  an external system, nondeterministic resource, or important test boundary may
  justify a seam with one production adapter.
- Dependency injection and pure return values help only when they reduce caller
  knowledge or isolate a real effect. Do not introduce them ceremonially.
- Side effects belong at explicit owned boundaries; they do not need to be
  hidden behind extra layers merely to enable mocks.
- Tests and callers should normally observe the same public contract. A need to
  test through internals is evidence that the seam or module shape is wrong.

## Return a design decision

Report the current problem, chosen responsibility and interface, direct
consumers, invariants and failure modes, test seam, rejected alternatives,
migration effect, and evidence that would invalidate the decision. Feed this
decision into `$create-plan` when it changes a delivery design; do not implement
or refactor unless the user requested that work through `$dev-loop`.
