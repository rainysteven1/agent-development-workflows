---
name: open-code-review
description: Use Alibaba OpenCodeReview after ordinary verification and an atomic commit to build a deterministic parent-to-commit file-and-rule manifest, then run a fresh time-bounded Luna adversarial review with complete coverage, structured synthesis, and commit-bound evidence.
---

# Open Code Review

Use `ocr review` as the formal per-commit verdict. Use `ocr delegate` only for optional file/rule
previews or an explicitly requested Luna second opinion. Required evidence still reviews one
immutable parent-to-commit range after ordinary verification; never combine commits or let a reviewer
freely explore unrelated history when the exact diff is sufficient.

Do not call `ocr llm test` or an unconfigured provider. `ocr review` is the maintained formal command;
an optional Luna second opinion is selected only for high-risk changes.

## Fixed Execution Contract

- Finish ordinary verification, staged-diff inspection, and the atomic commit before required
  adversarial review. Resolve and record the commit's single full parent SHA and full commit SHA;
  branch names, `HEAD`, and uncommitted work are not review evidence.
- Run `ocr review --commit <sha>` with pinned `--provider`, `--model`, and `--effort`, after a
  `--preview`. Require `terminal_state=complete`, every preview file in completed coverage, no
  failed/budget-skipped item, and disposition every finding. Record OCR version, provider, model,
  effort, session ID, rule fingerprint, and both SHAs.
- If preview marks a material changed file unsupported, excluded, or otherwise
  unreviewable, do not call that complete coverage. Preserve the OCR preview and
  use `ocr delegate preview` for the same immutable commit plus one fresh
  read-only Luna review of exactly those files. Record its session, terminal
  conclusion, coverage, and dispositions beside the formal OCR receipt. A
  silently skipped material file keeps the gate incomplete.
- For high-risk changes only, run one additional fresh Luna session against the same immutable
  packet. It is a second opinion and never replaces the OCR verdict.
- Keep the reviewer scoped to the requested diff and direct consumers. Do not expand into unrelated
  history or repositories. The default packet limit is 12 files and 800 changed lines; split an
  increment or define explicit bounded batches before invoking a larger review.
- Protect delivery time with the bundled runner. Reviews at or below 6 files and 200 changed lines
  get 180 seconds; larger permitted packets get 300 seconds. A timeout is `incomplete`, never
  acceptance. Preserve its artifacts and retry only after changing packet scope or invocation.
- A provider-capacity failure before any review reasoning may be retried once after 15 seconds with
  a fresh output prefix; both attempts must remain inside the original packet budget. A second
  capacity failure is `unavailable`, not a reason to switch model or keep polling. The bundled
  runner's pre-response Max watchdog may use its explicit XHigh fallback within the same total
  budget; ordinary `ocr review` retries do not invent that fallback.
- Treat workspace, multi-commit, MR-range, and Work-Package-range review as optional diagnostic
  modes that must be explicitly requested. None can substitute for a required per-commit gate or
  satisfy its Plane evidence contract.

## Bounded finding convergence

Freeze acceptance checks, direct consumers, and trust boundaries in the packet;
a reviewer cannot widen them. When `$long-horizon` is active, read and use
[../long-horizon/references/harness-contract.md](../long-horizon/references/harness-contract.md)
for finding identity, complete-set triage, evidence requirements, root-cause
grouping, remediation convergence, and degraded-mode continuation.

In ordinary mode, use the same evidence test: fix only a demonstrated current
acceptance/direct-effect violation; dismiss duplicate, out-of-scope, and
speculative findings with evidence and a reopen condition. Tests and explicit
acceptance remain the oracle; zero findings is never the loop target.

A timeout or interruption may resume the same immutable OCR session once. If
that resume also fails, preserve the artifacts and return `unavailable`; do not
start another equivalent provider session. Long-horizon may add exactly one
independent read-only fallback review under its contract. The fallback never
becomes an OCR receipt or Phase/WP completion evidence.

## Full-Context-First Fallback Protocol

When a task explicitly asks for a repository-wide or full-context review, use this
two-stage protocol. It is global policy and applies before choosing a smaller
packet; it does not widen the user's requested repository or commit range.

### Stage A — Full-context attempt

- Freeze the immutable review packet first: one parent SHA, one commit SHA, and
  the preview file set. A full-context attempt may use unrestricted file reads,
  repository search, and diff reads to inspect direct consumers and surrounding
  contracts.
- If it reaches a native complete terminal state with full coverage, preserve its
  report as the full-context result. It may satisfy the requested diagnostic
  review, but it does not by itself replace the formal `ocr review --commit`
  receipt required by this skill.
- Do not downgrade because the reviewer found a code defect. Findings enter the
  normal remediation loop. Downgrade only for an execution failure: context
  compression, timeout, provider-capacity failure, or another explicitly
  recorded infrastructure error.
- Preserve the failed session/output and classify the failure before retrying.
  Never repeat the same failing invocation unchanged. A provider-capacity error
  may use the one retry already defined above; after that, enter Stage B.

### Stage B — Incremental formal OCR plus Luna

If Stage A fails for an eligible execution reason:

1. Run formal `ocr review --commit <sha>` on deterministic bounded batches. Each
   batch requires its own preview, exact parent/commit SHAs, complete terminal
   state, and no failed or budget-skipped item. Keep the default packet ceiling
   (12 files and 800 changed lines), and split further for security,
   authorization, concurrency, schema, or deployment risk.
2. Union the batch coverage and deduplicate findings by stable file/line/rule
   identity. The formal gate passes only when every batch is complete and every
   finding is dispositioned; one incomplete batch makes the whole increment
   incomplete.
3. Start one fresh Luna cross-file second-opinion session against the same
   immutable packet. Ask it to inspect direct consumers, persistence/schema and
   authorization/tenant boundaries. If full-context Luna also compresses or
   times out, run Luna per deterministic batch and record that degradation.

The incremental OCR receipt is the formal gate. The Luna result is supplementary
and never changes the receipt or Plane state. Record the Stage A outcome and
failure class, every Stage B batch manifest, the Luna session(s), and the final
coverage matrix together in the task-owned evidence. Do not claim that a
degraded two-stage review was a successful full-context review.

### State machine and stopping rule

```text
FULL_CONTEXT_ATTEMPT
  ├─ complete/full coverage → formal commit receipt + optional Luna
  └─ compression/timeout/capacity failure
       → incremental formal OCR (all batches complete)
       → fresh Luna cross-file opinion
```

An ordinary zero exit code, partial JSON, missing preview item, or budget-skipped
batch is not acceptance. Stop at the first unpassed checkpoint and report the
failed edge, preserved artifact, and next changed diagnostic variable.
Under the explicit long-horizon OCR-outage exception, this stop applies to the
unreviewed behavior, dependent work, integration, and acceptance claims; an
independent local increment may continue with the preserved fallback evidence.

## Delegation Workflow

1. Verify the CLI without testing an OCR-side LLM:

   ```bash
   command -v ocr
   ocr --version
   ```

   Execute the formal OCR review directly:

   ```bash
   ocr review --commit <full-commit-sha> --audience agent --format json \
     --output /tmp/<task>-<commit>-ocr.json --provider crs-custom \
     --model gpt-5.6-luna --effort high --timeout 15
   ```

   Run `ocr review --preview` first; use `ocr review --resume <session-id>` only for an interrupted
   OCR session. Preserve the native JSON/SARIF manifest and result artifacts.

   `ocr review` and `ocr llm test` are not equivalent host-review sessions.
   They may also target a different API shape (for example, OCR chat
   completions versus a CRS Responses endpoint), so an OCR/provider error is
   diagnosed as an integration mismatch rather than evidence that Codex review
   is unavailable.

2. Fix the immutable target and business context. Verify the commit has exactly one parent and the
   local checkout contains both full revisions. Run OCR preview:

   ```bash
   ocr delegate preview --format json \
     --from <full-base-sha> --to <full-head-sha> \
     --background "<acceptance criteria and business context>"
   ```

   A bare workspace preview is permitted only for an explicitly requested development review.

3. Preserve OCR's native run manifest. Record the parent and commit SHAs, OCR version, provider,
   model, effort, session ID, rule fingerprint, every selected file, and each file's terminal status.

4. Keep one atomic commit packet at or below 12 files and 800 changed lines. Use a smaller atomic
   increment for security, authorization, concurrency, schema, or deployment changes. If one
   indivisible file exceeds the ceiling, record the reason and define explicit path/line batches;
   do not send an unbounded range to the built-in `review --commit` explorer.

5. Resolve rules for the packet when the repository requires a pinned rule file:

   ```bash
   ocr delegate rule --format json <batch-paths...>
   ```

   Keep the OCR `--rule` input and preview fingerprint in the receipt.

6. Inspect OCR JSON/SARIF. It must list every preview path exactly, have `terminal_state=complete`,
   no failed or budget-skipped item, and provide line-anchored findings plus a final verdict.

7. `terminal_state=complete` with full coverage is required; partial JSON or a zero exit code alone
   never passes. Record the OCR session ID and native manifest in the receipt.

8. Triage the complete finding set and persist normalized identities before editing. Group open
   blockers by root cause into the smallest coherent remediation, rerun ordinary checks, and start a
   fresh immutable OCR review for that remediation commit. For high-risk changes, add one fresh Luna
   second opinion; never carry coverage or synthesis across commits. Record the resolving revision for
   every fixed finding. `$long-horizon` owns progress/no-progress and interruption decisions; ordinary
   mode reports an unresolved accepted blocker after the documented diagnostic path is exhausted.

## Commit Receipt And Plane Phase Evidence

For every commit, copy `~/.codex/skills/plane-workflow/assets/commit-review.template.json` to a
task-owned temporary path. Record the full parent/commit SHAs, OCR version/provider/model/effort,
session ID, terminal state, preview file statuses, rule fingerprint, native command, and findings
disposition. Keep the manifest and receipt out of Git, then call `$plane-workflow`'s
`phase-record-commit-review` dry-run/apply command. Do not defer the OCR verdict until Phase closure.

The Phase command rejects workspace or symbolic revisions, wrong parents, incomplete OCR terminal
state/coverage, reused session IDs, incomplete synthesis, and undispositioned findings. A fixed finding
may name a later remediation commit; every such remediation commit still needs its own fresh receipt.
The WP later verifies that every commit in each real MR range is mapped to exactly one Phase with a
recorded review marker. Plane WP `Review` means those MRs exist; it never starts a WP-wide reviewer.

## Feature-group autosquash after acceptance

After one feature commit and all of its `fixup!` remediation commits have
complete accepted reviews and dispositioned findings, converge that group
before starting another independent feature. Never squash an entire WP, Phase,
branch, or MR merely because it is one delivery container.

Treat a squash as `history-only` only if all of the following hold:

- The branch is private or the user explicitly authorizes history rewriting;
- the final squashed tree is byte-identical to the last reviewed tree, proved by
  comparing immutable tree IDs (for example,
  `git rev-parse <reviewed-head>^{tree}` and
  `git rev-parse <squashed-head>^{tree}`), with no generated, dependency,
  submodule, or configuration changes;
- the target did not move in a way that introduced additional content, and no
  unresolved conflict or manual edit changed the reviewed tree; and
- every original commit has its own complete receipt and a dispositioned finding
  chain;
- every remediation subject targets the root feature commit with `fixup!`, the
  group is still at branch tip, and autosquash produces exactly one commit with
  the original feature parent and subject; and
- no later independent commit has had its parent-to-commit review boundary
  rewritten.

Under these conditions, do not invent a new OCR receipt for the final feature
commit. Preserve the original receipts unchanged and record a Plane Phase
provenance marker with:

- all original reviewed commit SHAs and their parent SHAs;
- the final squashed commit SHA and its parent SHA;
- the reviewed and squashed tree SHAs plus the exact equality command/output;
- the marker `history-only feature autosquash`, the operator, and the timestamp; and
- the statement that no source tree changed and the original receipts remain
  bound to their original commits.

The final commit is a new Git object, so old receipts must never be relabeled as if
they were generated for the new SHA. If tree equality, target stability, or
authorization cannot be proven, treat the result as a new commit increment:
run preview and formal `ocr review --commit` again, then obtain any required
Luna second opinion. The same rule applies to a rebase, conflict resolution,
generated-file refresh, delayed reordering across another feature, or any other
operation that changes the final tree or reviewed commit boundary.

## Commit Boundary

Required delivery review follows an actual atomic commit and ordinary verification. Do not create a
commit merely because review was requested, infer one commit per Phase, combine several commits for
one review, or invoke
`$commit-generate` merely because a Phase reached Done. An explicitly requested uncommitted review
remains development-only.
