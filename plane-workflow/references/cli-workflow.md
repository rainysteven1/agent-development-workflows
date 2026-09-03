# Plane Workflow CLI

## Contents

- [Route contract](#route-contract)
- [Plan contract](#plan-contract)
- [Read sequence](#read-sequence)
- [Write sequence](#write-sequence)
- [Legacy and superseded work](#legacy-and-superseded-work)
- [Phase execution](#phase-execution)
- [Commit, MR, and merge evidence](#commit-mr-and-merge-evidence)
- [Commands](#commands)

## Route contract

Keep shared Plane transport and credentials in `~/.config/surveying/plane.env`, owned by the current
user with mode `600`. It contains exactly `PLANE_BASE_URL` and `PLANE_API_KEY`. Keep repository
ownership in `.plane-workflow.json`, or declare the same five values explicitly in the closest
`AGENTS.md`: workspace slug, project UUID, project identifier, exact project name, and
`external_source`.

Copy `assets/repository-route.template.json` to `.plane-workflow.json` when free-form `AGENTS.md`
text cannot be resolved unambiguously. The CLI walks from the requested repository to its Git root,
prefers `.plane-workflow.json`, and otherwise parses the closest `AGENTS.md`. It never guesses from
directory or product names.

Run this first:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py route --repo "$PWD"
```

## Plan contract

Copy `assets/work-package.template.json` into a task-owned temporary location, replace every
example and placeholder, and remove the top-level `"template": true` safety marker. Validation and
every sync refuse the marker or any remaining `CHANGE-ME`, `WP-XXA`, or `YYYY-MM-DD` placeholder.
The JSON describes semantic planning input, not Plane UUID payloads.
Declare the complete affected repository set in `work_package.repositories` using canonical
`group/repository` slugs. The rendered WP description preserves this set, and MR/merge receipts reject
an omitted or additional repository.
The CLI derives:

- Module external ID: `module:<requirement-id>`
- Requirement external ID: `requirement:<requirement-id>`
- Work Package external ID: `work-package:<wp-id>`
- Phase external ID: `phase:<wp-id>:<number>`
- Work Package label: the exact Work Package ID

One Work Package maps to one coherent delivery capability and may own one Merge Request per affected
repository. Each material commit is reviewed independently and recorded on its actual Phase; there is
no WP- or MR-range adversarial review. Phase boundaries are acceptance slices, not commit boundaries.
Do not create one commit per Phase or invoke `$commit-generate` unless a real atomic increment exists.

When one Requirement contains sibling Work Packages, declare the same `requirement.priority`,
`requirement.start_date`, and `requirement.target_date` envelope in every sibling plan. Keep each
`work_package` date range independently accurate and inside that Requirement envelope. Plans that
omit the Requirement scheduling fields retain the single-WP behavior and inherit the Work Package
values.

Validate before any Plane read or write:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py validate-plan /tmp/work-package.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py render-plan /tmp/work-package.json
```

## Read sequence

Use one deterministic inspection instead of manually composing searches:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py inspect-project --repo "$PWD"
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py inspect-work-package --repo "$PWD" --wp-id WP-01A
```

The client reads the Plane connection from process `PLANE_BASE_URL` and `PLANE_API_KEY` overrides,
then the single canonical `~/.config/surveying/plane.env`. `PLANE_CONNECTION_FILE` may explicitly
select another secure file for isolated tests. The loader rejects non-regular files, another user's
file, group/world permissions, unknown or duplicate keys, and missing values. It holds the key only
in memory and never prints it. Repository routing always overrides process defaults. The client honors proxy
environment variables; if that proxy explicitly returns HTTP 407, it retries the same Plane host
once without the proxy and reports the transport event. Set `PLANE_REQUIRE_PROXY=1` where policy
forbids that fallback.

For classified transient TLS EOF, connection reset/abort, or timeout failures, the client makes at
most three attempts for an idempotent GET without extending the per-attempt timeout. Certificate,
HTTP, DNS, and configuration failures are not retried.

## Write sequence

`sync-work-package` computes a read-only reconciliation plan by default. Add `--apply` only after
reviewing that plan. Apply mode resolves or creates the Module and label, reconciles Requirement,
Work Package, and Phase work items by external ID then exact name plus parent, adds the complete
hierarchy to the Module, and re-reads every object.

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py sync-work-package \
  /tmp/work-package.json --repo "$PWD"
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py sync-work-package \
  /tmp/work-package.json --repo "$PWD" --apply
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py verify-hierarchy \
  /tmp/work-package.json --repo "$PWD"
```

Never use `--apply` when route verification is incomplete, the project identity conflicts, or the
read-only reconciliation contains an ambiguous match.

Mutations are never retried automatically after a transport error. Re-read the target first and
issue only an idempotent reconciliation for fields proven missing.

For a started legacy Work Package whose description predates the participating-repository section,
use the narrow metadata migration. It appends only the missing section, refuses to rewrite an
existing repository set, and re-reads every Phase to prove its state and evidence are unchanged:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py migrate-work-package-repositories \
  --repo "$PWD" --wp-id WP-03A --repository platform/delivery-platform
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py migrate-work-package-repositories \
  --repo "$PWD" --wp-id WP-03A --repository platform/delivery-platform --apply
```

Do not use this command to replace a non-empty repository set or to rewrite a Phase description.

For a previous plan that is entirely Backlog/unstarted with zero checked tasks and no actual
evidence, remove its Requirement/WP/Phase hierarchy before syncing a replacement:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py delete-unstarted-work-package \
  /tmp/replacement-work-package.json --repo "$PWD"
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py delete-unstarted-work-package \
  /tmp/replacement-work-package.json --repo "$PWD" --apply
```

The replacement plan supplies the stable Module, Requirement, and WP identities. The command keeps
the Module for later reconciliation, deletes Phase children before their WP and Requirement, and
re-reads after each mutation. It refuses started/completed/cancelled items, any checklist/evidence,
unexpected descendants, partial Module membership, or cross-Module membership. Use legacy marking,
not deletion, as soon as any Phase has execution evidence.

After regrouping several never-started single-WP Modules, retire only an old Module proven empty:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py retire-empty-module \
  --repo "$PWD" --module-id REQ-OLD --successor REQ-NEW \
  --reason 'Its Work Packages now belong to the grouped Requirement.'
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py retire-empty-module \
  --repo "$PWD" --module-id REQ-OLD --successor REQ-NEW \
  --reason 'Its Work Packages now belong to the grouped Requirement.' --apply
```

The command refuses non-empty Modules and any status other than `planned`; apply marks the exact
Module `[已取代]` and `cancelled`, preserves it as an audit record, and re-reads both fields and empty
membership. It never deletes a Module.

## Legacy and superseded work

Do not delete or rewrite completed Phase evidence when a product boundary moves. Use the fixed
legacy transition after inspecting the WP:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py mark-legacy-work-package \
  --repo "$PWD" --wp-id WP-01A --mode superseded \
  --successor 'REQ-002 / WP-02A' --reason 'The product boundary moved to the successor.'
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py mark-legacy-work-package \
  --repo "$PWD" --wp-id WP-01A --mode superseded \
  --successor 'REQ-002 / WP-02A' --reason 'The product boundary moved to the successor.' --apply
```

`historical` requires the WP and all direct Phases to be Done; it keeps their states and checklist
evidence and marks the Module completed. `superseded` preserves semantically complete Done Phases,
cancels only unfinished direct Phases, and cancels the WP, Requirement, and Module. Both modes append
an idempotent successor marker to high-level descriptions and update high-level names. The command
refuses detached Phases, partial Module membership, multiple Modules, or a Requirement with sibling
WPs. After an uncertain mutation, run the same command without `--apply` to re-read drift before any
reconciliation.

## Phase execution

Start a Phase with one update and post-write read:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-start \
  --repo "$PWD" --wp-id WP-01A --phase 0 --apply
```

Render the ignored local ledger from the same plan and keep item-by-item evidence there:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py render-ledger \
  /tmp/work-package.json --phase 0
```

Before completing a Phase, export its final semantic HTML to a task-owned file. `phase-complete`
requires the exact current task count/order/text, preserved goal and acceptance sections, both Plane
checkbox markers, and non-placeholder `实际证据`. Without `--apply` it reports the intended update.
With `--apply` it sends one description/state PATCH and re-reads both state and semantic content.

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-summary --html-file /tmp/phase.html
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-complete \
  --repo "$PWD" --wp-id WP-01A --phase 0 --html-file /tmp/phase.html --apply
```

## Commit, MR, and merge evidence

Commit review occurs inside `$dev-loop`. Immediately after each material commit's OCR verdict is
complete and accepted or fully resolved, copy `assets/commit-review.template.json`, remove its template
marker, and fill the exact parent/commit SHA, Phase, repository, OCR version/provider/model/effort,
session ID, terminal state, preview coverage, rule fingerprint, and findings. Record it on the actual
Phase before starting another planned commit:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-record-commit-review \
  --repo "$PWD" --wp-id WP-01A --phase 1 --receipt /tmp/commit-review.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py phase-record-commit-review \
  --repo "$PWD" --wp-id WP-01A --phase 1 --receipt /tmp/commit-review.json --apply
```

The command rejects symbolic revisions, non-parent ranges, repositories outside the WP, stale or
uncontained commits, incomplete OCR terminal/coverage evidence, a reused session within the WP,
incomplete synthesis, and undispositioned findings. A finding-remediation commit gets its own OCR
receipt. Phase completion must preserve commit and session markers.

After all Phases are Done, create one real MR per declared repository when authorized. Use `glab mr
create` for the operator action and re-read immutable MR state and revisions with:

```bash
python ~/.codex/skills/plane-workflow/scripts/gitlab_workflow.py inspect-mr \
  --repo "$PWD" --iid 123
```

Copy `assets/work-package-mr.template.json`, record each opened MR, and map every commit in each exact
base-to-head chain to one Phase containing that commit's receipt. Then move the WP to Review using a
dry-run and one apply:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py work-package-review-start \
  --repo "$PWD" --wp-id WP-01A --receipt /tmp/wp-mrs.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py work-package-review-start \
  --repo "$PWD" --wp-id WP-01A --receipt /tmp/wp-mrs.json --apply
```

The command refuses incomplete Phases, a stale checkout head, missing or duplicate repositories/MRs,
an incomplete Git chain mapping, or a commit whose review marker is absent from the mapped Phase.
`WP Review` means the real MR set exists and awaits merge. It is not review evidence and never starts
a WP-wide Luna session.

After all recorded MRs merge, re-read each MR, update every target checkout to the reported immutable
merge revision, and run post-merge regression plus real usage. Copy
`assets/work-package-merge.template.json` and use `merge` or `fast_forward` for ancestry-preserving
merges. For squash merges, set `merge_method: squash` and record GitLab's full `squash_revision`.
Then close the WP with dry-run and apply:

```bash
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py close-work-package \
  --repo "$PWD" --wp-id WP-01A --receipt /tmp/wp-merge.json
python ~/.codex/skills/plane-workflow/scripts/plane_workflow.py close-work-package \
  --repo "$PWD" --wp-id WP-01A --receipt /tmp/wp-merge.json --apply
```

The close gate requires the WP already in Review, the same recorded MR URL/base/head set, merged
states from GitLab, matching target checkout revisions, integrated revision ancestry, and concrete
post-merge commands plus real usage. Only then does the WP become Done; the Requirement and Module
close when all sibling WPs meet their own gates.

GitLab handoff remains human-controlled. This workflow does not create project webhooks, receivers,
or review Runners because none can replace the host-agent's per-commit OCR gate. Once a commit's OCR
receipt is accepted, use `glab` only for an explicitly authorized push, MR mutation, or merge,
then re-read the MR with `inspect-mr`. Treat any separately requested event automation as an
independent `$dev-loop` task rather than an implicit Plane capability.

## Commands

Run `plane_workflow.py --help` or `<command> --help` for the maintained argument contract. Every
live write command is dry-run unless `--apply` is explicit. The only deletion command is
`delete-unstarted-work-package`, with the never-started and evidence-free gates described above.

For the documented self-hosted Page fallback, list Pages first without an owner or identity:

```bash
python ~/.codex/skills/plane-workflow/scripts/ensure_self_hosted_page.py \
  --context <context> --namespace <namespace> --target <api-workload> \
  --workspace <workspace> --project-id <project-uuid> --list
```

Inspect by an exact Page UUID, external identity, or unambiguous exact name. `--export-html` writes
the full UTF-8 HTML only to a new local file and verifies its reported length and SHA-256; Page HTML
is not printed. Candidate HTML terminal CR/LF characters are normalized because the Plane serializer
does not retain them. Inspection also returns the existing Page creator/updater UUIDs so an explicit
owner can be selected for a later apply. Supplying `--html-file` without `--apply` reports the exact
target and old/new hashes without mutation:

```bash
python ~/.codex/skills/plane-workflow/scripts/ensure_self_hosted_page.py \
  --context <context> --namespace <namespace> --target <api-workload> \
  --workspace <workspace> --project-id <project-uuid> \
  --page-id <page-uuid> --external-source <source> --external-id <stable-page-id> \
  --html-file <semantic.html>
```

Creation or update requires the same exact selectors plus `--owner-id`, `--html-file`, and
`--apply`:

```bash
python ~/.codex/skills/plane-workflow/scripts/ensure_self_hosted_page.py \
  --context <context> --namespace <namespace> --target <api-workload> \
  --workspace <workspace> --project-id <project-uuid> --owner-id <user-uuid> \
  --name '<page-name>' --external-source <source> --external-id <stable-page-id> \
  --html-file <semantic.html> --apply
```

The helper refuses ambiguous names or external identities, mismatched selectors, locked Page
updates, existing export targets, inactive or cross-workspace owners, serializer normalization
drift, and missing apply prerequisites. Existing Pages are updated with Plane's
`PageDetailSerializer(partial=True)` and the Page transaction task. Before mutation it verifies the
owner's active target-workspace membership, locks the Project and its current Page rows, and
revalidates every supplied selector. The serializer's persisted HTML must remain byte-identical to
the normalized candidate; otherwise the atomic mutation exits with a normalization conflict and no
transaction is queued. The transaction receives the persisted HTML, not a pre-serializer copy.
Afterward the helper re-reads the project-scoped Page and verifies selector uniqueness, identity,
and exact HTML SHA-256. A mutation is never retried automatically. If transaction enqueueing fails
after the serializer save, the helper returns exit 6 and reports the applied instance hash even when
the immediate database re-read also fails, so the caller can re-read before any reconciliation.
Non-result remote stdout and stderr are never replayed; only their line count, byte count, and
SHA-256 are reported.

The maintained commit/MR/merge commands and close sequence are defined in
[Commit, MR, and merge evidence](#commit-mr-and-merge-evidence). Do not substitute raw Plane PATCHes
or a WP-range reviewer for those gates.
