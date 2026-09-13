# Delivery outcome and supporting work

Use this contract for ordinary and autonomous delivery, including review-driven
work. `dev-loop` owns this scope and admission policy; `long-horizon` retains
ownership of autonomous run states, failure signatures, and human interrupts.
OCR owns review execution and receipts. None of these tools defines the user's
product requirements.

## Fix the outcome before optimizing the means

Keep one short record in the existing task ledger:

- `outcome`: the user's final observable result, including the requested handoff;
- `must_now`: current acceptance IDs and the smallest end-to-end check for each;
- `next_outcome_check`: the next real usage or integration observation to obtain;
- `not_now`: optional improvements and later work, with concrete reopen triggers;
- `evidence`: observed failures, source-proven reachable defects, or hypotheses;
- `budget`: relevant owning modules and justified additions to state, retries,
  abstractions, dependencies, and verification scope; and
- `finish`: required checks, review coverage, and authorized external gates.

An intermediate artifact has only the obligations needed by this outcome and
its current supported consumers. A helper, test harness, SDK wrapper, migration
script, or review integration does not become a general-purpose product merely
because implementing it produces another commit. If building a reusable tool is
itself requested, its specified supported cases are part of `must_now`.

Derive the record from the authorized request and active plan. Later phases and
review suggestions do not expand it. Bring later work forward only for a proven
current dependency; reconcile a required planning change before implementation.
Never shrink an explicit requirement or weaken existing supported behavior to
fit the budget. Zero new mechanisms is the default; justify relevant additions
with a current caller or measured constraint. Omit irrelevant budget dimensions.

## Admit work by its effect on delivery

Before a supporting improvement or review-driven edit, record:

1. The current outcome/acceptance ID or existing supported behavior at risk.
2. The current caller and permitted input, state, or interleaving that triggers it.
3. The observable violation and causal link to that outcome or direct regression.
4. The cheapest source check, existing test, or usage probe and its actual result.
5. The disposition and the minimum corrective action, if any.

Use the same gate for code, tests, docs, configuration, automation, and tools.
Source-level causal proof is sufficient; a production incident is unnecessary.
Required security, authorization, data integrity, accessibility, and recovery
constraints remain obligations even when the happy path succeeds.

Choose one disposition:

- **Current blocker:** a demonstrated violation of the fixed outcome, a direct
  regression for an existing supported consumer, or a required safety boundary.
  Group by root cause and fix the smallest owning mechanism.
- **Evidence gap:** required verification or review is missing. Obtain that
  evidence through the existing path; change only the owning verification
  artifact when it is demonstrably defective. This does not authorize unrelated
  production changes or converting incomplete review into acceptance.
- **Deferred/dismissed:** optional generality, hypothetical consumers, stronger
  tests without missing current evidence, style, or already-resolved concerns.
  Record the reason and reopen trigger; continue the next outcome step without
  editing, creating a cleanup commit, or requesting another review for this item.

A reviewer comment starts as a candidate, not an instruction. Disposition the
whole finding set read-only before remediation. Severity labels, a reachable
helper path, or an isolated failing artificial test do not alone establish the
delivery link. Preserve evidence for concrete defects in current shared users;
do not dismiss them merely because they are outside the happy path.

## Bound cumulative detours

Track supporting work against the same outcome across commits, phases, review
sessions, and compaction. Before each further repair, name which outcome check
it unblocks and why a simpler existing path cannot satisfy the same contract.
Once that prerequisite works, exercise the consuming path before improving it
again. A green helper test, cleaner commit, new receipt, or fewer comments alone
does not prove that the user's result works.

After two consecutive supporting repair/review cycles without advancing an
outcome check or removing a demonstrated blocker, stop that supporting strategy
before another edit. Re-evaluate the full path: discard optional work, reuse an
existing adequate mechanism, or redesign the smallest proven blocking owner.
Persist the detour count, last outcome evidence, and changed approach; renaming
findings, changing files, or making a new commit does not reset the count.
New causal evidence may justify a changed bounded approach; unrelated local
improvement does not. This checkpoint changes the strategy, not acceptance,
authority, or the requirement to continue safe in-scope work.

If a proposed addition exceeds the complexity budget, re-examine the owning
layer before stacking mechanisms. Revise the budget only with evidence that the
simpler approach cannot meet current acceptance. Do not create a universal
line-count, test-count, or total-remediation cap that hides real defects.

## Keep tool recovery within the task

Classify a tool failure separately from a product defect. Use maintained help,
status, or logs for a bounded diagnosis and follow its documented retry limit.
Do not automatically start improving the tool, its provider, caches, or workflow
policy. A local tool correction is in scope only with a demonstrated necessary
dependency, no adequate existing route, and the same admission record above.
Tool-wide redesign requires its own requested scope.

Use an existing authorized alternative only when it meets the same required
evidence and safety contract. Do not invent a successful receipt or bypass a
mandatory gate. If required infrastructure remains unavailable, preserve the
failed edge, complete independent outcome work, and report the exact pending
gate and recovery trigger; autonomous mode uses its existing degraded states.
Do not replace the pending user outcome with an open-ended tool-maintenance task.

## Finish at the requested result

When checks and required reviews pass, execute the next authorized outcome step
or handoff. Stop optional hardening. Missing bookkeeping calls for evidence
reconciliation, not new behavior or repeated accepted reviews. Report what now
works for the user, the remaining outcome edge if any, and its evidence; commit
counts and review rounds are not the progress measure. An example such as
deployment does not authorize deployment in an unrelated workflow-edit task.
