---
name: grill-me
description: Explicitly stress-test a consequential plan, design, or decision before action. Use only when the user invokes $grill-me or directly asks to be grilled; do not trigger for routine clarification or ordinary implementation.
---

# Grill Me

Turn an important but unsettled direction into a decision-complete input. This
is a read-only interview: do not implement, publish a plan, or mutate project
state during the session.

## Build the decision tree

Separate facts from decisions. Resolve facts from the workspace, maintained
documentation, or available tools instead of asking the user. Put only choices
that require product, architecture, risk, cost, or priority judgement to the
user.

Model dependencies between decisions. A question is ready only after the
choices it depends on are settled. In each round, ask up to three ready
questions and include:

- the decision and why it changes the result;
- mutually exclusive options with their material tradeoffs;
- a recommended option grounded in known constraints.

Wait for the user's answers before expanding dependent branches. Recompute the
remaining decision tree after every round. Challenge contradictions and vague
answers with concrete scenarios instead of accepting them silently.

## Keep the interview bounded

Cover every unresolved choice that could change scope, public interfaces, data
or ownership boundaries, security posture, migration/rollback behavior, or
acceptance criteria. Do not pursue wording preferences or hypothetical future
branches that cannot change the current delivery.

When talking cannot resolve a choice, identify the cheapest prototype,
measurement, or evidence-gathering action that would resolve it. Record that as
an open prerequisite; do not guess or perform the action unless separately
authorized.

## Finish with a decision ledger

End only when the material frontier is empty or each remaining decision has an
owner and explicit defer condition. Return:

- settled decisions and rationale;
- verified facts and sources;
- assumptions that remain unverified;
- rejected alternatives and why;
- open prerequisites, owners, and reopen conditions;
- candidate observable acceptance checks.

Ask the user to confirm the shared understanding. After confirmation, the
ledger may become input to `$create-plan`; this skill never performs that
handoff implicitly.
