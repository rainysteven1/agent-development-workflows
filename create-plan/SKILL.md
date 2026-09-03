---
name: create-plan
description: Create an evidence-backed delivery brief for a non-trivial coding design after its direction is sufficiently settled. Use when the user asks for a plan, implementation design, or Plane-ready brief; do not use for a simple checklist or mutate Plane.
---

# Create Plan

Produce one reviewable design authority candidate before decomposition or
implementation. Work read-only unless the user separately asks to save the
brief. `$plane-workflow` owns every Plane or Page mutation.

## Establish the input

Read the closest instructions and maintained repository entrypoints. Separate
verified facts, constraints, assumptions, and unresolved decisions. Inspect the
current flow, direct consumers, and existing contracts before proposing a
replacement.

Use the smallest planning depth that fits the task:

- a small reversible change needs scope, approach, risks, and checks;
- a material feature needs the complete delivery brief below;
- a high-risk change also needs trust boundaries, failure recovery, migration,
  and rollback.

If a consequential choice is unresolved, expose it instead of hiding it in an
implementation step. Use `$grill-me` only when the user explicitly requests a
grilling session.

## Delivery brief

Include the sections that carry decisions for this task:

1. **Status and objective**: mark the brief `Draft`; state the user-visible
   outcome and why it matters.
2. **Facts, constraints, assumptions**: cite current sources and distinguish
   what remains unverified.
3. **Current flow and consumers**: identify the affected path, authorities, and
   direct callers or operators.
4. **Proposed design**: describe responsibilities, interfaces, data/state
   transitions, failure behavior, and observability.
5. **Alternatives**: record only credible alternatives and the evidence-based
   reason each was rejected.
6. **Scope and non-goals**: bound the current delivery without dropping required
   tests, docs, migrations, accessibility, security, or generated artifacts.
7. **Security and recovery**: when untrusted input, authentication,
   authorization, secrets, privileged operations, network entrypoints,
   migrations, or third-party dependencies are involved, identify trust
   boundaries, abuse/failure paths, rollback, and required evidence.
8. **Acceptance map**: assign stable IDs `AC-1`, `AC-2`, and so on. For each,
   name an observable result, the intended verification mechanism, and the
   likely delivery slice. Every required outcome must map to evidence.
9. **Delivery slices and dependencies**: order vertical, independently
   verifiable capabilities. Do not equate slices with commits.
10. **Open decisions**: name the owner and the condition required to resolve or
    defer each one.

Do not prescribe code that repository discovery has not justified. Name likely
files and commands only when current evidence supports them.

## Quality gate and handoff

Before presenting the brief, confirm that each acceptance ID is observable,
each slice exercises a real caller path, risks have owners, and no assumed
future consumer created an abstraction or switch.

The user approves or revises the `Draft`. When Plane publication is requested
or established, pass the approved brief to `$plane-workflow`: the full design
belongs on the project Page, while the Requirement, Work Package, and Phases
carry the delivery summary and `AC-*` mappings. Plane becomes the execution
authority only after those writes are read back and verified.

After that authority switch, a material change to scope, interface, data
ownership, trust boundary, recovery behavior, or acceptance criteria must be
reconciled in Plane before dependent implementation continues. Chat text never
silently overrides the verified plan.
