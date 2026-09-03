---
name: writing-for-agents
description: Design or audit agent-facing instructions such as AGENTS.md, CLAUDE.md, complex Skill bodies, and agent runbooks. Use when trigger routing, context load, information hierarchy, authority, or completion behavior matters; do not use for ordinary human prose or routine Skill metadata.
---

# Writing for Agents

Write instructions that make the intended behavior easy to select, execute,
and finish without loading unrelated context. `$skill-creator` owns Skill
packaging and structural validation; this skill owns instruction architecture.

## Design the route

Start with intended behavior, authority, inputs, outputs, and observable finish
conditions. List representative prompts that must trigger the instructions and
nearby prompts that must not. Resolve overlaps with existing instructions before
adding another route.

A context pointer such as a Skill description or an `AGENTS.md` link must name
the material and the distinct situations that require it. Front-load the main
use case so matching survives truncation. Use one phrase per real branch rather
than many synonyms for the same branch, and include a boundary when neighboring
work could misroute.

## Place information deliberately

Use the lightest durable layer that preserves behavior:

1. always-loaded instructions contain stable constraints and short routing;
2. the main Skill contains steps and rules every invocation needs;
3. references hold substantial branch-specific material loaded only when that
   branch applies;
4. scripts own repeated deterministic mechanics that prose would reimplement
   unreliably;
5. current code, configuration, and `--help` remain the source for cheap facts
   that would otherwise become stale documentation caches.

Keep a concept's definition, constraints, and completion criterion together.
Avoid a chain of pointers when the next action is always required.

## Make execution checkable

- Write imperative steps with explicit inputs, outputs, authority boundaries,
  and stopping conditions.
- End each material step with a condition the agent can observe, not a vague
  instruction to understand, handle, or be thorough.
- Distinguish facts, assumptions, decisions, and permissions.
- Prefer positive target behavior. Keep negative rules only for a real hazard or
  likely misroute, and pair them with the safe action.
- Keep one source of truth for each rule. Remove duplicate wording, stale
  environment facts, historical explanation, and instructions that do not
  change behavior.
- Preserve necessary security, destructive-action, privacy, and authorization
  guardrails even when they add context.

## Validate behavior

After structural validation, exercise a small prompt matrix:

- positive cases that should load the instructions;
- negative cases that should remain on another route;
- overlap cases that prove precedence between Skills;
- authority cases that ensure read-only requests do not mutate state;
- completion cases that distinguish real evidence from a success claim.

Inspect the actual behavior and revise only demonstrated routing or execution
failures. A regex match, valid frontmatter, or polished wording does not prove
that an agent follows the workflow.

For a repository change, keep `$dev-loop` as the delivery controller. For Skill
creation or packaging, use `$skill-creator` after the instruction contract is
settled.
