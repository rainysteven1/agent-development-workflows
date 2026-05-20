---
name: paper-craft
description: "Use when writing, structuring, or polishing a research paper in LaTeX or a paper-as-code workflow. Covers outline building, section drafting, figure linkage, claim-evidence consistency, revision tracking, and camera-ready checks. Trigger on paper drafting, section writing, figure integration, rebuttal prep, or paper polishing. 中文触发：写论文、LaTeX、润色论文、组织结果、rebuttal、camera-ready。"
---

# Paper Craft

## Overview

Treat the paper as a reproducible artifact. Claims, figures, and numbers should stay linked to the experiments that support them.

## Workflow

1. Build the argument outline before polishing prose.
2. Draft sections in dependency order.
3. Attach each major claim to supporting evidence.
4. Keep figures reproducible from data.
5. Re-run consistency checks before submission or revision.

## Core Checks

For each claim:

- is there direct evidence for it
- is that evidence actually referenced
- do the numbers in text match the source results

For each figure or table:

- is it cited in the paper
- is its message explicit in nearby text
- can it be regenerated from code or data

## Revision Mode

When responding to reviews:

- track comments explicitly
- map each change to affected files
- separate real paper edits from response-letter-only items

## Handoff

- use `plotting` for publication-quality figures
- use `talk-architect` when converting the paper into a talk story
