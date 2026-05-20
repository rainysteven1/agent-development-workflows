---
name: weekly-report
description: "Use when the user wants a weekly work report or commit-based activity summary. Gather commits from the current repo or selected GitHub repos, group them by outcome, merge noisy follow-up commits, and produce a concise Chinese or English report. Trigger on \"weekly report\", \"周报\", \"what did I do this week\", \"summarize my commits\", or similar requests."
---

# Weekly Report

## Overview

Generate a work report from commit history, not memory. The output should describe completed outcomes, not a raw commit log.

## Scope Rules

- Default to the current repo if the user does not specify scope.
- Accept a custom time range when provided.
- For GitHub-wide summaries, use `gh` if available and authenticated.

## Workflow

1. Collect commits for the requested window.
2. Drop merge commits and bot noise.
3. Merge small follow-up commits into the main work item.
4. Group by theme, not chronology.
5. Write result-oriented bullets.

## Categories

Useful default buckets:

- Feature
- Fix
- Refactor
- Docs
- Infra
- Research

## Output Rules

- Prefer Chinese when the conversation is in Chinese.
- Each bullet should describe a finished outcome.
- If commit messages are unclear, inspect changed files or diff summaries before writing.
- Keep the report concise enough to paste directly into chat or a work log.

## Command Hints

- Current repo: `git log --since=<date> --no-merges --oneline`
- GitHub API: `gh api` or `gh search commits`

If `gh` is unavailable, fall back to local git history and say so.
