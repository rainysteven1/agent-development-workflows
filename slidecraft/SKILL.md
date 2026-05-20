---
name: slidecraft
description: "Use when creating, revising, or diagnosing academic slide decks, especially code-authored slides or structured presentation workflows. Covers visual system choices, slide composition, density control, reveal logic, and rendered-deck debugging. Trigger on slide generation, deck revision, layout fixes, or slide visual-system work. 中文触发：做幻灯片、改 deck、slide 布局、PPT 视觉、渲染检查。"
---

# Slidecraft

## Overview

This skill handles deck implementation and diagnosis. Its core rule is progressive disclosure: each slide should expose only what the audience can process at that moment.

## Entry Checklist

Before editing slide code or a structured deck source, confirm:

- the talk plan is stable enough
- the visual system is known or needs definition
- the main presentation quality targets are clear

## Workflow

1. Define or consume the visual system.
2. Build reusable layout patterns.
3. Compose slides around one main message each.
4. Integrate figures and diagrams after structure is clear.
5. Render and inspect the output.
6. Fix the smallest real cause of any visual defect.

## Diagnosis Rules

When slides look wrong:

- classify the issue first: overflow, density, alignment, contrast, reveal logic
- change the smallest responsible element
- re-render before touching unrelated structure

## Handoff

- use `talk-architect` before this skill when the story is still unstable
- use `pptx` when the task is native `.pptx` IO, splitting, merging, or artifact QA
