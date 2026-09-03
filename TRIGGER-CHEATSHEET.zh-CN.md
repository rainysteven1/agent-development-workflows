# Agent Skill 路由速查

这是自研开发管理 Skill 套件的短路由图。每次只加载当前任务真正需要的 Skill。

## 日常开发默认路线

```text
需要自主推进       long-horizon
需要 Plane 状态    plane-workflow
明确要求压力测试   grill-me（仅显式调用）
需要交付设计简报   create-plan
模块接口或 seam    codebase-design
实现或修改         dev-loop + lean-delivery
陌生仓库           guide + existing-project
范围或调用链不清楚 repo-evidence
生成原子提交信息   commit-generate
提交后正式审查     open-code-review
Push/MR/合并       finishing-a-development-branch
```

`dev-loop` 控制完整实施流程；`git-workflow-and-versioning` 负责 Git 边界，
`using-git-worktrees` 负责隔离工作区。

## 按问题选择

| 需求 | Skill |
| --- | --- |
| 读取仓库规则和维护入口 | `guide` |
| 固定目标、指标和取舍 | `north-star` |
| 显式要求挑战重大决策 | `grill-me` |
| 生成有证据的交付设计简报 | `create-plan` |
| 设计模块接口、所有权和测试 seam | `codebase-design` |
| 新建项目或子系统 | `new-project` |
| 恢复陌生仓库地图 | `existing-project` |
| 查代码、调用者、依赖和影响面 | `repo-evidence` |
| 管理跨会话或团队 Memory | `memory-governance` |
| 实现、修复、重构和交付 | `dev-loop` |
| 少打断、按边界自主推进 | `long-horizon` |
| 控制范围、避免过度设计 | `lean-delivery` |
| 管理目标分支、提交和版本 | `git-workflow-and-versioning` |
| 创建或复用隔离 worktree | `using-git-worktrees` |
| 生成一个原子提交的信息 | `commit-generate` |
| 对不可变 commit 做 OCR 审查 | `open-code-review` |
| Push、MR、合并和清理 | `finishing-a-development-branch` |
| 管理 Plane WP/Phase 和证据 | `plane-workflow` |
| 设计风险驱动的 Rust 测试 | `rust-testing` |
| 恢复 Codex active-writer 会话 | `codex-session-writer-recovery` |
| 诊断端口和进程启动链 | `witr-diagnose` |

## 研究路线

```text
想法 -> research-ideation -> experiment-lab -> plotting/paper-craft
     -> research-comm -> talk-architect -> slidecraft/pptx
```

基于提交生成周报时使用 `weekly-report`。

## 边界

AnySearch、Workbuddy、Paseo、Lark、视觉包以及其他 marketplace Skill 属于外部安装工具，
不由这个仓库维护，也不复制进来。
