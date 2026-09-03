# Plane Format Reference

Use these templates as semantic HTML. Plane may add editor classes and `data-id` attributes after saving; do not generate or preserve those incidental attributes.

## Hierarchy

```text
Module: <requirement ID> · <requirement title>
└── Requirement work item: <requirement ID> · <title>
    └── Work Package: WP-XX[A-Z] · <delivery title>
        ├── Phase 0 · <phase title>
        ├── Phase 1 · <phase title>
        └── Phase N · <phase title>
```

Add the requirement, WP, and Phase work items to the Module. Parent relationships still carry the canonical hierarchy.

## Work Package Description

```html
<h3>目标</h3>
<p>描述这个 Work Package 最终关闭的业务或架构缺口。</p>

<h3>设计边界</h3>
<ul>
  <li><p>说明事实源、所有权或不可跨越的边界。</p></li>
  <li><p>说明复用哪些现有 authority/contract，不建立什么第二套模型。</p></li>
  <li><p>说明 mock、live、provider 或仓库之间的责任分界。</p></li>
</ul>

<h3>交付范围</h3>
<p>概括 Phase 的推进顺序和交付切片，不复制每条 Phase checklist。</p>

<h3>总体验收</h3>
<p>写一个从用户或真实调用方角度可观察、可判定的完成条件。</p>
```

One WP owns one coherent delivery capability and may span multiple repositories, with one MR per
affected repository. Declare their canonical `group/repository` slugs in
`work_package.repositories`; the rendered `参与仓库` section is the authority used to reject missing
or unexpected repository entries. Review every actual material commit inside `$dev-loop` and record
its commit-bound receipt on the actual Phase before another planned commit. At WP Review, map each MR
commit back to those Phase records; do not run a combined WP or MR-set adversarial review. Split
independently acceptable or independently releasable work into separate WPs.

## Initial Phase Description

```html
<h3>目标</h3>
<p>说明本 Phase 完成后新增的可观察能力。</p>

<h3>具体任务</h3>
<ul data-type="taskList">
  <li data-type="taskItem" data-checked="false">
    <label><input type="checkbox"><span></span></label>
    <div><p>第一项可独立验证的任务。</p></div>
  </li>
  <li data-type="taskItem" data-checked="false">
    <label><input type="checkbox"><span></span></label>
    <div><p>第二项可独立验证的任务。</p></div>
  </li>
</ul>

<h3>验收标准</h3>
<p>描述必须通过的行为、约束、环境或 usage pass。</p>

<h3>证据</h3>
<p>待本 Phase 完成后回填真实测试与运行证据。</p>
```

## Completed Phase Description

Keep the original goal and acceptance criterion. Mark every proven task with both `data-checked="true"` and `checked`:

```html
<h3>目标</h3>
<p>保留原目标。</p>

<h3>具体任务</h3>
<ul data-type="taskList">
  <li data-type="taskItem" data-checked="true">
    <label><input type="checkbox" checked=""><span></span></label>
    <div><p>已验证完成的任务。</p></div>
  </li>
</ul>

<h3>验收标准</h3>
<p>保留原验收标准。</p>

<h3>实际证据</h3>
<ul>
  <li><p><code>targeted test command</code> 通过，说明覆盖的行为。</p></li>
  <li><p>真实 usage pass：调用入口、环境、可观察结果与稳定 reason code。</p></li>
  <li><p>首次失败暴露的问题、根因和修复；不要只记录最终绿色结果。</p></li>
  <li><p>格式、race、restart、安全或其他当前 Phase 验证的真实结果。</p></li>
</ul>

<h3>明确边界</h3>
<p>仅在确有 deferred hardware、credential、HIL 或外部审批时保留本节。</p>
```

## Evidence Rules

Good evidence is exact and attributable:

- exact test/build command and pass/fail result;
- database/runtime state observed through the authority system;
- real API, UI, CLI, device, restart, replay, or failure-path usage;
- failures found during the Phase and the corrective change;
- explicit unverified boundaries and why they remain deferred.

Do not use:

- “all tests passed” without naming the relevant gate;
- “see repository/source ledger”;
- planned evidence presented as actual evidence;
- raw secrets, session tokens, activation codes, credentials, or fences;
- commit/MR links as the only behavioral proof.

## Dates and States

- Use realistic sequential dates based on dependencies and effort; do not assign every Phase the same day mechanically.
- Initial Phase state is the project's unstarted/backlog state.
- Set a Phase In Progress immediately when work starts.
- Update checklist and evidence before setting Done.
- Start the next Phase only after the preceding Phase is verified Done, unless parallel execution is explicit.
- Record every accepted or fully resolved commit review on its actual Phase before the next planned
  commit. Preserve those markers when completing the Phase.
- After all direct Phase children are Done and every real MR is created and recorded, set the WP to
  Review. Review means the MR set awaits merge; it never starts a WP-wide reviewer.
- Keep OCR out of CI. Every material commit must already have its own immutable parent-to-commit OCR
  manifest, unique Luna Max reviewer, bounded batches, same-session synthesis, and dispositions.
- Set the WP Done only after every recorded MR is re-read as merged and post-merge regression plus
  real usage pass against the exact target revisions.
- Set the Module completed only after all Work Packages in the requirement are complete.
- Do not map Phase boundaries to commits. Invoke `$commit-generate` only for an actual requested or
  required commit boundary.

## Labels

Use the Work Package identifier itself as a label, such as `WP-07C`, on the WP and its Phases. Reuse an existing label by exact name; create it only if absent. Preserve any project-wide domain or priority labels already in use.

## Idempotent Synchronization Checklist

Before creation:

1. Find the project and Module.
2. Find the requirement work item.
3. Search external IDs and name-plus-parent for the WP and Phases.
4. Resolve state IDs and labels.

After creation/update:

1. List Module work items.
2. Confirm every expected item belongs to the Module.
3. Confirm Phase parent is the WP and WP parent is the requirement.
4. Confirm names, dates, priority, label, description, and state.
5. Reconcile mismatches; never create duplicate replacement items.
