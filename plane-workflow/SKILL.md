---
name: plane-workflow
description: Turn a delivery brief into a deterministic Plane hierarchy of Module, Requirement, cross-repository Work Package, and independently verifiable Phases, then inspect, reconcile, execute, aggregate per-commit review evidence, and close it with stable IDs, repository routing, dry-run-first automation, and post-write verification. Use for Plane planning, phased TODO execution, closure transitions, commit-review evidence aggregation, progress inspection, evidence closure, or repeated Plane API work. 中文触发：设计 Plane 层级、生成 Phase TODO、查看当前 Phase、同步 Plane、执行阶段、聚合逐 commit 审查证据、回填证据、关闭 WP、固定 Plane 脚本。
---

# Plane Workflow

Use Plane as the planning authority and the bundled CLI as the default Plane harness. Do not
recompose searches, UUID lookups, HTML task lists, or update payloads by hand when a maintained
command covers the operation.

Keep the shared Plane connection in the single canonical file
`~/.config/surveying/plane.env`, owned by the current user with mode `600`. It contains only
`PLANE_BASE_URL` and `PLANE_API_KEY`. Never copy it into a repository or duplicate either value in
repository-local Codex config. The CLI loads it in memory and never prints either value.

## Load The Relevant Contract

- Read [references/repository-plane-routing.md](references/repository-plane-routing.md) before the
  first Plane call in a repository.
- Read [references/plane-format.md](references/plane-format.md) before creating or rewriting a Work
  Package or Phase description.
- Read [references/cli-workflow.md](references/cli-workflow.md) before using the Python harness or
  changing its templates.

## Resolve And Inspect First

Run the route resolver before any Plane call:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py route --repo "$PWD"
```

The route must resolve repository path, workspace slug, project UUID, project identifier, exact
project name, and `external_source` from `.plane-workflow.json` or the closest `AGENTS.md`. Never
infer ownership from a product name, directory parent, current MCP process, or user-level default.

Use the fixed read paths instead of repeated discovery calls:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py inspect-project --repo "$PWD"
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py inspect-work-package \
  --repo "$PWD" --wp-id WP-01A
```

Report Phase progress as `checked/total; current=<first unchecked>; remaining=<count>`. Treat Plane
state and task-list HTML as authority; chat, commits, and local notes are not progress evidence.

## Build A Work Package

When the input is an approved `$create-plan` delivery brief, preserve its full
design on a project Page when Pages are requested or already established. Write
and verify that Page before creating the hierarchy. Keep detailed rationale on
the Page; summarize only the delivery boundary in the Requirement and Work
Package. Preserve every stable `AC-*` identifier: include the complete set in
`work_package.acceptance`, prefix each Phase acceptance with the identifiers it
covers, and ensure every required identifier belongs to at least one Phase.
Plane becomes the execution authority only after the Page and hierarchy are
read back and verified.

An approved design from another source may enter the same route. Normalize it
read-only into the required delivery-brief fields and stable `AC-*` identifiers
without reopening settled decisions. If a missing field would require a new
product, architecture, security, or acceptance decision, stop before mutation
and surface only that blocking decision; do not silently invent it.

If implementation later changes approved scope, public interfaces, data
ownership, trust boundaries, recovery behavior, or an `AC-*` criterion, stop
the dependent Phase and reconcile the Page plus affected hierarchy before
continuing. A chat message or local ledger does not silently replace Plane.

Copy `assets/work-package.template.json` to a task-owned temporary path. Replace every example and
every `CHANGE-ME`/`WP-XXA`/`YYYY-MM-DD` placeholder, remove its `"template": true` safety marker,
then validate and render it:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py validate-plan /tmp/work-package.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py render-plan /tmp/work-package.json
```

Keep this hierarchy:

```text
Project
└── Module · one requirement delivery boundary
    └── Requirement work item
        └── WP-XXA · one coherent delivery boundary
            ├── Phase 0 · independently verifiable slice
            └── Phase N · independently verifiable slice
```

Treat one Work Package as one coherent delivery capability. It may span multiple repositories and
therefore own one MR per affected repository; record those MRs as one delivery set without reviewing
their combined range. Split only
independently acceptable or independently releasable capabilities into separate Work Packages. A
Phase is an acceptance and dependency slice, not a commit boundary; several Phases may share one
commit, and one Phase may require several commits. Never create or request a commit merely because a
Phase starts or ends.

One Work Package owns one worktree set: one isolated task worktree for each
affected repository, all labelled with the same WP identity. Do not interpret a
cross-repository WP as one filesystem worktree. Reuse each repository's
canonical project map and evidence baseline through `$existing-project` and
`$repo-evidence`; creating a WP worktree does not trigger full onboarding.
When a repository has managed index lifecycle configuration, `git worktree add`
triggers its owned post-checkout preparation hook. Record and verify the
revision-keyed task state for every member of the set before graph-dependent
Phase work; repair a missing/failed state through `$repo-evidence`, not by
copying caches ad hoc.

Add the Requirement, WP, and every Phase to the Module. Preserve parent relationships as the
canonical hierarchy. Use these external IDs:

- Module: `module:<requirement-id>`
- Requirement: `requirement:<requirement-id>`
- Work Package: `work-package:<wp-id>`
- Phase: `phase:<wp-id>:<number>`

For sibling Work Packages under one Requirement, give every sibling plan identical
`requirement.priority`, `requirement.start_date`, and `requirement.target_date` values covering the
full Requirement delivery window. Keep each Work Package's own dates independently accurate inside
that envelope. A single-WP plan may omit these fields and inherit its Work Package schedule.

Preserve the repository's `external_source`. Use the WP ID itself as the label on the WP and all
Phases. Declare every affected forge repository in `work_package.repositories` as a unique canonical
`group/repository` slug; the rendered WP description makes this the authoritative MR set expected at
review. Give every Phase 2-5 tasks, one observable acceptance criterion with its `AC-*` mapping,
realistic sequential dates, and explicit boundaries when later work could be confused with current
scope.

Apply the capability pyramid: smallest real happy path, durable state/basic observation, first real
integration, then failure/security/recovery/scale hardening. Use 1-9 Phases; do not force a fixed
count. Do not put `TODO` in titles or create child work items for ordinary checklist details.

## Reconcile Without Duplicates

Run a read-only reconciliation first; writes require explicit `--apply`:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py sync-work-package \
  /tmp/work-package.json --repo "$PWD"
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py sync-work-package \
  /tmp/work-package.json --repo "$PWD" --apply
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py verify-hierarchy \
  /tmp/work-package.json --repo "$PWD"
```

When an approved design changes after a Phase has started, use the narrow design reconciler instead
of `sync-work-package`. It updates only the existing WP and Phase descriptions; it never changes the
Module, Requirement, hierarchy, dates, states, priorities, or labels. An active Phase may change only
its `明确边界`; its goal, task list, acceptance criterion, and recorded review/history markers must
remain unchanged. Unstarted Phases must have no progress or evidence, and terminal or review Phases
cannot be changed. Dry-run first, then apply and re-read every changed item:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py \
  reconcile-work-package-design /tmp/work-package.json --repo "$PWD"
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py \
  reconcile-work-package-design /tmp/work-package.json --repo "$PWD" --apply
```

The command preflights the full mutation set, but Plane offers no multi-item transaction. If apply
stops after an uncertain PATCH, do not roll back or retry the write blindly; run the same command
without `--apply` to re-read the hierarchy, then apply only the remaining deterministic actions.

Reconcile by `external_source + external_id`, then exact name plus parent. Stop on ambiguous matches.
Create or update in dependency order: Module and label, Requirement, WP, Phases, Module membership.
Do not delete an object except through the guarded never-started replacement flow below. Never
create a replacement after an uncertain write or continue downstream after a failed edge. Every
apply command must re-read and verify the current project revision and result.

When a newly planned hierarchy has never started and its product boundary is wrong, delete its
Requirement, WP, and Phases before syncing the replacement plan. Preserve the Module so the new plan
can rename/reconcile it, and use the replacement plan to fix the exact identities:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py delete-unstarted-work-package \
  /tmp/replacement-work-package.json --repo "$PWD"
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py delete-unstarted-work-package \
  /tmp/replacement-work-package.json --repo "$PWD" --apply
```

The command refuses any started/completed/cancelled state, checked task, actual evidence, unexpected
child, detached Phase, ambiguous identity, or cross-Module membership. It deletes child-first,
re-reads after every DELETE, leaves the Module unchanged, and treats an already absent hierarchy as
verified recovery. Never use it for a WP with completed or partial execution evidence.

When regrouping leaves an old Module empty, use `retire-empty-module` with dry-run then `--apply`.
It requires the exact Module external identity, `planned` status, zero membership, a stable successor,
and a concrete reason. It preserves the Module as `[已取代]` / `cancelled` audit history and never
deletes it. Do not hand-write a Module PATCH.

When a product boundary replaces an existing single-WP Module, preserve completed Phase evidence and
use the legacy command instead of deleting objects or hand-writing PATCH requests:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py mark-legacy-work-package \
  --repo "$PWD" --wp-id WP-01A --mode superseded \
  --successor 'REQ-002 / WP-02A' --reason '<why the authority moved>'
```

Use `historical` only when the WP and every direct Phase are already Done. Use `superseded` to keep
Done Phases unchanged and cancel only unfinished direct Phases, then mark the WP, Requirement, and
Module with the successor. Review the dry-run actions before adding `--apply`; the command requires a
single-WP Requirement and exact Module membership across every Module, including Phase-only
conflicts; it never deletes evidence and re-reads every PATCH.

## Execute One Phase At A Time

1. Start the selected Phase with `phase-start --apply`; re-read the state before implementation.
2. Render `assets/phase-ledger.template.md` with `render-ledger` into the repository's ignored
   `docs/todo/` path. This task-owned ledger is the item-by-item execution record, not a second Plane
   authority.
3. When the Phase performs cross-module refactoring, deletion, or explicitly relies on Graft or
   another structural index, invoke `$dev-loop`'s structural-index contract before the first
   graph-based scope decision. Resume from the repository's recorded canonical baseline when valid;
   seed or refresh task-local Graft when that structural baseline exists. Only when no reusable
   Graft baseline exists may explicit index-creation authority initialize structural state at the
   whole task worktree root. This fallback never creates or copies a Zvec-Grep index. Otherwise
   refresh/check at the exact Phase-start revision. Record tool, revision,
   root, language/file coverage, freshness result, and compiler/raw-search/external-consumer blind
   spots in the local ledger. Refresh again before a later checklist item relies on graph evidence
   made stale by earlier Phase commits. A post-commit/merge/checkout hook may record only a
   worktree-local stale marker; never treat hook success or a tool's automatic query refresh as Phase
   evidence. Phase evidence requires the maintained blocking refresh/check on a clean exact HEAD.
4. Execute exactly one checklist item through the repository development loop: implement, targeted
   test, real usage when applicable, staged-diff inspection, atomic commit, per-commit OCR and fresh
   time-bounded Luna review, feedback/fix, and evidence. A checklist item may still require several
   commits. If bounded OCR retry is unavailable and `$long-horizon` applies, preserve the failed
   manifest and independent fallback review locally, continue only checklist work independent of the
   unreviewed behavior, and leave that commit's Plane receipt and Phase completion pending until
   formal OCR recovers.
5. Update only the local ledger after the item. Record state, commands, results, runtime observations,
   failures, cleanup, and next action. Keep Plane checklist items unchecked while the Phase is open.
6. Keep failed, blocked, and deferred items visible. A retry must preserve the earliest error,
   demonstrated cause or labeled hypothesis, cleanup result, and changed diagnostic variable.
7. After every item and the Phase acceptance criterion pass, prepare one final semantic HTML
   description. Check every item with both Plane checkbox markers and replace `证据` with `实际证据`.
8. Run `phase-complete` without `--apply`, inspect the intended transition, then apply it once. The
   command requires the exact current task count/order/text, preserves the current goal and
   acceptance criterion, refuses partial markers or empty/placeholder evidence, and re-reads the
   final HTML plus Done state.
9. Start the next sequential Phase only after the current Phase is verified Done in Plane.

Do not PATCH Plane item by item. Do not batch several Phases into one completion update. Keep later
hardening in the ledger's `延期` section without executing or counting it in the current Phase. A
Phase boundary neither creates a commit nor triggers review, but every actual material commit inside
the Phase normally finishes `$dev-loop`'s OCR and fresh-reviewer gate before another planned commit
begins. The only exception is `$long-horizon` continuation after bounded OCR infrastructure failure:
preserve the failed manifest and exact-commit fallback review, continue only independent local
reversible work inside the same active Phase, and leave dependent work, Phase advancement, the formal
receipt, and Phase completion pending. Do not defer a working review service merely for convenience
or replace missing receipts at Work Package completion.

## Record Commit Evidence And Close The Work Package

Immediately after one material commit's OCR review is complete and its findings are accepted or fully
resolved, copy `assets/commit-review.template.json` to a task-owned temporary path and record the
SHA-bound receipt on the Phase where that commit belongs. The receipt records OCR version,
provider/model/effort, session ID, terminal state, preview coverage, rule fingerprint, and findings.
For high-risk changes, attach a separate fresh Luna second-opinion receipt; it is not the default gate.
Dry-run first, then apply before starting another planned commit:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-record-commit-review \
  --repo "$PWD" --wp-id WP-01A --phase 1 --receipt /tmp/commit-review.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-record-commit-review \
  --repo "$PWD" --wp-id WP-01A --phase 1 --receipt /tmp/commit-review.json --apply
```

The receipt must name the exact parent and commit SHAs, actual Phase and declared repository, native
OCR command and manifest metadata, complete file coverage, terminal state, session ID, and every
finding disposition. A remediation commit is the only allowed next commit while an increment is
unaccepted; it gets its own OCR receipt. Phase completion preserves these markers. Never reuse a
session or defer recording until WP closure.

When an accepted feature commit has one or more accepted `fixup!` remediation
commits, autosquash that feature group before starting another independent
feature. Copy `assets/history-rewrite.template.json`, preserve every original
receipt under its original SHA, and record the content-neutral mapping with
dry-run then apply:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-record-history-rewrite \
  --repo "$PWD" --wp-id WP-01A --phase 1 --receipt /tmp/history-rewrite.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-record-history-rewrite \
  --repo "$PWD" --wp-id WP-01A --phase 1 --receipt /tmp/history-rewrite.json --apply
```

The command requires a contiguous feature-plus-fixup chain, every original OCR
marker plus its complete validated receipt on that Phase, fixup subjects
targeting the root feature, an immediate final HEAD with the original
parent/subject, and exact reviewed/final tree
equality. It writes an additional provenance marker; it never rewrites or
relabels an OCR receipt. Any failed invariant requires fresh verification and
OCR for the resulting commit. GitLab whole-MR squash does not satisfy this
feature-group contract.

After all direct Phases are Done, create or update one real GitLab MR per affected repository when
that handoff is authorized. Use `glab mr create` for the operator action and re-read each MR through
the maintained helper:

```bash
python ~/.codex/skills/plane-workflow/scripts/gitlab_workflow.py inspect-mr \
  --repo "$PWD" --iid 123
```

Render `assets/work-package-mr.template.json` with the exact MR URLs, opened state, base/head SHAs,
inspection commands, and a complete commit-to-Phase mapping for each linear MR range. Every mapped
commit must already have review evidence or a validated history-only rewrite marker on that Phase.
Embed the complete `commit_review_receipt` for an unchanged reviewed commit, or
the complete `history_rewrite_receipt` for a rewritten commit, in its MR mapping.
The CLI revalidates the receipt and recomputes the marker; a marker-shaped
string alone is never evidence.
Record the MR set and move the WP to `Review`
with dry-run then apply:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py work-package-review-start \
  --repo "$PWD" --wp-id WP-01A --receipt /tmp/wp-mrs.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py work-package-review-start \
  --repo "$PWD" --wp-id WP-01A --receipt /tmp/wp-mrs.json --apply
```

`WP Review` means the recorded MRs exist and await merge. It is not a WP-wide adversarial review and
does not replace any commit review. Run final cumulative regression and cross-repository real usage
against the exact MR heads. If this produces a commit, complete and record that commit's own review
before regenerating the MR receipt.

After every recorded MR is merged, re-read its state and merge/squash revision from GitLab, update the
target checkout to that immutable revision, and run post-merge verification plus real usage. Render
`assets/work-package-merge.template.json`, then run `close-work-package` without `--apply`, inspect the
gate, and apply it once:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py close-work-package \
  --repo "$PWD" --wp-id WP-01A --receipt /tmp/wp-merge.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py close-work-package \
  --repo "$PWD" --wp-id WP-01A --receipt /tmp/wp-merge.json --apply
```

The close gate requires the same MR set already recorded on the WP, every MR in `merged` state, exact
target revisions, and post-merge verification. Use `merge` or `fast_forward` when the MR head is an
ancestor of the merge revision. Use `squash` only with GitLab's full `squash_revision`, which must be
an ancestor of the merge revision. When all sibling WPs pass the same gate, the command closes the
Requirement and Module with a re-read after each edge. Preserve external approval, credential,
hardware, HIL, CI, deployment, or runtime gates as explicit unpassed checks.

Keep GitLab handoff human-controlled. Do not provision project webhooks, event receivers, or review
Runners as part of this workflow: they cannot satisfy or replace the local per-commit OCR/Luna gate.
After review evidence is accepted, push, create or update the MR, and merge only with the user's
applicable authorization. Use `glab` for those explicit operator actions and the maintained
`inspect-mr` command for read-back evidence. If the user separately requests event automation, treat
it as its own `$dev-loop` implementation with independent acceptance and security boundaries.

## Page Exception

Use project Pages only for durable design context when requested or already established. Try the
project-scoped public Page route selected by the repository. On a self-hosted release documented to
lack that route, use `scripts/ensure_self_hosted_page.py`; do not probe repeatedly, use raw SQL, or
ask the user to recreate a tool-supported action in the UI. Use `--list` to discover project Pages,
then select one with an exact Page UUID, external identity, or unambiguous exact name. The helper is
read-only by default: it can inspect metadata and hashes, export full HTML to a new local file, and
compare `--html-file` as a dry-run. `--apply` requires an owner and HTML, rejects ambiguity,
identity conflicts, and locked Pages, uses Plane's Page serializers, and re-reads the exact HTML
SHA-256 plus identity before returning `verified`. Continue Module and Work Item work independently
if the cluster-backed Page route is genuinely out of scope.

For Page apply, supply a user who is active and has an active membership in the target workspace.
The helper rejects cross-workspace or inactive identities. It also rejects any serializer HTML
normalization not already handled by the local input normalizer before committing or enqueueing the
Page transaction.

## Evidence And Safety

- Keep requirements, dates, state, checklist, and acceptance evidence in Plane; keep code and tests
  in Git; keep durable repository behavior in indexed docs.
- Keep OCR delegation out of CI. CI evidence and independent review evidence are separate gates.
- The CLI retries only idempotent GET requests after classified transient TLS EOF, connection
  reset/abort, or timeout errors. It never automatically retries a mutation; after an uncertain
  write, re-read Plane and reconcile only fields proven missing.
- Use exact test/build commands, runtime observations, stable reason codes, and real usage results.
  Never present planned evidence as actual evidence.
- Never place secrets, tokens, credentials, private keys, local proxy addresses, or claim fences in
  Plane, templates, ledgers, command output, or repository files.
- Treat timeouts as symptoms. Locate the waiting layer and earliest error before changing timeout,
  retry, or backoff values.
- Prefer the CLI. Use raw MCP calls only for a capability the harness does not expose, and preserve
  the same route, idempotency, dry-run, ordering, and post-write verification rules.
