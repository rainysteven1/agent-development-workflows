---
name: diagnosing-bugs
description: Prove the root cause of a hard, intermittent, recurring, cross-layer, or performance failure before fixing it. Use when the cause is uncertain or prior fixes failed; do not invoke the full workflow for a direct error whose cause is already demonstrated.
---

# Diagnosing Bugs

Turn an uncertain failure into a reproducible causal explanation. Diagnosis is
read-only by default. If the user asked only for diagnosis, stop after the root
cause packet; implementation requires separate authority and runs through
`$dev-loop`.

## Triage the failure

Capture the exact reported symptom, environment, earliest actionable error,
recent relevant change, and known-good comparison. A direct error may take the
short path when current evidence already proves its source: reproduce or verify
the failure, trace the causal edge, and return the root cause packet without
running ceremonial phases.

Use the full loop when the symptom is intermittent, slow, remote, cross-layer,
misleading, or resistant to a first evidence-based explanation.

## Build a tight feedback loop

Create one command or bounded procedure that exercises the actual failing path
and distinguishes the reported symptom from nearby failures. Prefer, in order:

1. a focused failing test;
2. a CLI, HTTP, or browser reproduction with an assertion;
3. a captured request, event, trace, or fixture replay;
4. a minimal harness around the responsible subsystem;
5. a seeded stress, differential, or bisection loop;
6. a structured human-in-the-loop procedure when automation is impossible.

Tighten it until it is specific, repeatable, fast enough to iterate, and safe
to run unattended where possible. For flakes, raise and measure the
reproduction rate instead of pretending a single pass is deterministic.

When the environment cannot reproduce the issue, exhaust safe in-scope checks,
then request the smallest redacted artifact, access, or temporary
instrumentation needed. You may form labeled hypotheses to guide collection;
do not present them as a cause.

## Minimize and hypothesize

Remove inputs, steps, configuration, and dependencies one variable at a time,
keeping only elements required for the failure. Then produce three to five
ranked hypotheses when the remaining cause is still ambiguous. Each hypothesis
must predict an observation that can falsify it.

Test one prediction at a time. Prefer a debugger or targeted boundary probe;
for performance, establish a measured baseline and use profiling, query plans,
or bisection instead of broad logging. Tag temporary instrumentation with a
unique marker. Redact secrets, tokens, credentials, and sensitive payloads from
commands, artifacts, and reports.

## Prove the root cause

A root cause packet contains:

- the original and minimized reproduction;
- the causal chain from trigger to observed symptom;
- the decisive observation and the hypothesis it confirmed;
- material alternatives that were falsified;
- affected consumers and trust boundaries;
- the smallest source-level correction, if a fix was requested;
- the correct regression seam or the demonstrated absence of one.

The immediate failing line is not automatically the root cause. Trace invalid
data, state, timing, ownership, or configuration backward until the source that
can prevent recurrence is identified.

## Fix handoff and stopping rule

When a fix is authorized, turn the minimized symptom into a red regression test
through `$tdd` when a correct seam exists, then implement through `$dev-loop`.
Re-run the original unminimized loop, the regression test, and the impacted
suite. Remove every tagged probe and reconcile temporary resources.

Count evidence-backed fix attempts. If three distinct corrections fail, do not
attempt a fourth. Revalidate the feedback loop, revisit previously falsified
hypotheses with the new evidence, and use `$codebase-design` to inspect seams,
shared state, and ownership. Escalate any consequential architecture choice to
the user before more implementation.
