---
name: pptx
description: "Use for PPTX-native workflows such as reading existing `.pptx` files, extracting text, editing templates, unpacking Office XML, combining or splitting decks, and final artifact QA on generated presentations. Use this instead of slidecraft when the deck itself is already a `.pptx` artifact rather than code-authored source. 中文触发：读取 pptx、改模板、拆分合并 PPT、Office XML、PPT 成品检查。"
---

# PPTX

## Overview

This is the artifact-level presentation skill. Use it when the source of truth is an actual `.pptx` file rather than slide code.

## Use Cases

- extract content from an existing deck
- inspect or diff slide text
- edit a template-backed presentation
- unpack and patch Office XML
- combine or split decks
- run final QA on a generated presentation artifact

## Workflow

1. Inspect the existing deck.
2. Choose the least fragile editing path.
3. Make the requested changes.
4. Render or extract content for QA.
5. Check for missing text, placeholders, overflow, and ordering issues.

## Routing Rule

- use `slidecraft` for deck design and structured slide-source work
- use `pptx` for `.pptx` artifact IO and QA

## QA Rule

Assume the first generated artifact has defects until checked. Verify both content and visual output before calling the deck done.
