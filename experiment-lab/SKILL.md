---
name: experiment-lab
description: "Use when planning, running, comparing, or organizing research experiments. Tracks experiment plans, baselines, run metadata, ablations, and cross-run comparisons so results stay traceable and reusable for papers or talks. Trigger on experiment execution, ablation design, result comparison, and experiment management. 中文触发：实验、ablation、对比结果、实验设计、跑实验、记录结果。"
---

# Experiment Lab

## Overview

The main job is traceability. Every result should be explainable months later: what idea it tested, what code produced it, what config changed, and why the result mattered.

## Workflow

1. Start from a validated idea or explicit experiment question.
2. Define variables, baselines, and controlled conditions.
3. Create a run plan before execution.
4. Store each run with metadata, metrics, and notes.
5. Compare runs against the success criteria, not just against each other.
6. Record the decision: proceed, refine, pivot, or abandon.

## What To Capture Per Run

- code version or commit
- config and dataset
- environment and seeds
- metrics in machine-readable form
- anomalies or interpretation notes

## Ablation Rule

Use ablations to isolate contribution, not to generate extra tables for their own sake. Start with single-variable removals before exploring interactions.

## Output Artifacts

- plan doc
- run directory with metadata and metrics
- comparison table
- changelog or decision note

## Handoff

- to `paper-craft` when the evidence is mature enough for writing
- to `research-comm` when results need discussion with advisor or coauthors
