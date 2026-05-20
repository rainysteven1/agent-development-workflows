---
name: research-comm
description: "Use when preparing advisor updates, coauthor discussions, group meetings, or research status messages. Extracts the few decisions, anomalies, pivots, and blocked items that are actually worth discussing from experiments, idea logs, and paper progress. Trigger on meeting prep, research updates, advisor communication, or discussion planning. 中文触发：组会、汇报、和导师讨论、进展更新、讨论准备。"
---

# Research Communication

## Overview

This skill is about extraction, not decoration. The goal is to compress ongoing research into the few points that deserve another person's attention.

## What Is Worth Discussing

- decisions that need input
- unexpected results
- blocked progress
- pivots or story changes
- evidence that changes paper direction

Routine implementation progress usually does not belong in the meeting core.

## Workflow

1. Read the actual artifacts: experiment notes, idea docs, paper status, decision logs.
2. Pull out candidate discussion points.
3. Rank them by urgency and importance.
4. Build a short background alignment block.
5. Present each point with context, evidence, options, and your recommendation.

## Default Output Shape

For each point:

- title
- why it matters
- evidence
- options or recommendation
- requested input

## Handoff

- to `talk-architect` or `slidecraft` if the format should become slides
- to plain text if this is just a written status update
