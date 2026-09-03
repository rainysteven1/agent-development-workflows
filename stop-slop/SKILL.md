---
name: stop-slop
description: Polish human-facing technical prose such as READMEs, guides, release notes, and design narratives by removing AI-sounding filler without changing facts. Do not use for agent instructions, code comments, API/schema reference, legal text, or commit messages.
---

# Stop Slop

Make formal technical prose sound deliberate, concrete, and specific while
preserving everything readers need to act safely. This is a semantic-preserving
editing pass, not permission to shorten away content.

## Preserve meaning first

Apply this priority order:

1. technical correctness;
2. required constraints, qualifications, warnings, and attribution;
3. repository terminology and established voice;
4. reader task success and navigability;
5. removal of generic AI patterns.

Keep code blocks, commands, paths, identifiers, links, tables, API names,
normative words, examples, and quoted material exact unless the user requested
technical changes to them. Do not turn cautious evidence into certainty or
marketing claims into facts.

## Detect signals, not forbidden tokens

Revise prose when these patterns add no information:

- throat-clearing or structure announcements before the actual point;
- empty emphasis, manufactured urgency, or pull-quote endings;
- vague claims such as robust, seamless, comprehensive, significant, or
  powerful without a named behavior or measurement;
- business jargon where a concrete verb exists;
- repeated summaries that restate the preceding paragraph;
- formulaic contrasts, rhetorical questions, or stacked sentence fragments;
- repetitive sentence lengths, paragraph shapes, or three-part rhythms;
- passive or abstract phrasing that hides an actor readers need to identify.

These are review signals, not blanket bans. Passive voice is valid when the
actor is irrelevant; adverbs can encode a real condition; lists may contain any
number of necessary items; punctuation follows repository style; and systems,
APIs, data, or markets may be grammatical subjects when that wording is
technically accurate.

## Editing workflow

1. Identify the document's audience, task, facts, and required sections.
2. Read nearby maintained prose to recover the project's voice and terms.
3. Remove filler and duplication, then replace vague claims with observable
   behavior, evidence, or a narrower statement.
4. Improve headings and ordering around the reader's actual journey: purpose,
   prerequisites, action, verification, failure handling, and next step.
5. Compare the revision with the source. Restore every lost constraint,
   qualifier, warning, attribution, command, and useful example.
6. Run the repository's applicable documentation checks and link or command
   validation when the requested edit includes them.

Return the revised prose or patch plus any factual claim that could not be
verified. Do not silently rewrite technical behavior to make the text smoother.
