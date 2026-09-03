---
name: commit-generate
description: Draft a concise Conventional Commit message from one already scoped change. In dev-loop, use only after an atomic increment is staged and its complete staged diff has been inspected. For standalone message requests, accept an explicit diff, file list, or summary. This skill never chooses commit boundaries, stages files, commits, or rewrites history.
---

# Commit Generate

Turn one reviewed change into a commit message that explains its intent and
material effects without inventing context.

## Pipeline contract

When invoked by `$dev-loop`:

- use the complete `git diff --cached` as the source of truth
- require the staged content to represent one atomic increment
- stop and return a boundary problem when the diff mixes independent reasons
  to change, unrelated formatting, user baseline, or unexplained files
- never stage, unstage, split, amend, commit, or run a destructive Git command
- return only the raw commit message so it can be reviewed and passed directly
  to the repository's normal commit command

Commit boundaries are owned by `$git-workflow-and-versioning`. A polished
message must not hide a non-atomic diff.

## Standalone input priority

For a message-only request outside `$dev-loop`, use inputs in this order:

1. an explicitly supplied diff or patch
2. staged changes from `git diff --cached`
3. a supplied changed-file list
4. a supplied natural-language summary

Do not silently fall back from an empty staged diff to unrelated unstaged
changes. State which source was used when it is not obvious from the request.

## Infer the message

### Identify the primary intent

Choose the type that represents why the change exists:

- `feat`: new user or caller capability
- `fix`: correction of incorrect behavior
- `refactor`: structural change without intended behavior change
- `perf`: performance improvement
- `test`: test-only change
- `docs`: documentation-only change
- `style`: formatting or presentation with no behavior change
- `ci`: CI workflow change
- `build`: build system or dependency packaging change
- `chore`: maintenance that fits no more specific type
- `revert`: an explicit reversal of an earlier commit

Use repository-native types when its maintained conventions differ.

### Choose a scope conservatively

Use the narrowest stable package, service, command, feature, or subsystem name
that dominates the change. Prefer repository conventions over path guesses.
Omit the scope when no single meaningful scope exists.

### Extract material effects

Prioritize observable or contract-relevant changes:

- behavior and failure-mode changes
- API, schema, configuration, or command changes
- validation, authorization, resource ownership, or lifecycle changes
- dependency or build effects
- tests that protect the new behavior or regression

Aggregate repetitive edits. Do not narrate whitespace, mechanical renames, or
every touched file unless that is the actual purpose of the commit.

### Remove commit-message slop

Use concrete verbs and named effects. Generic subjects such as `update`,
`improve`, or `enhance` are acceptable only when the object and observable
change make the intent specific. Remove meta-openers such as `this change`, and
drop unsupported polish words such as `properly`, `robust`, `comprehensive`, or
`seamless`.

The header states the primary intent. Body bullets add distinct rationale,
contract effects, failure behavior, or verification-relevant facts; they do not
paraphrase the header. Technical terms, passive voice, punctuation, and list
length follow clarity and repository convention rather than a generic prose
ban.

### Detect breaking changes

Mark a change as breaking only when the evidence shows an incompatible released
or explicitly supported contract. Then use both:

- `!` after type or scope in the header
- a `BREAKING CHANGE:` footer that states the impact and required migration

Do not infer a breaking change merely from an internal rename or unreleased
branch-local churn.

## Output format

Default to English and Conventional Commit form:

```text
<type>(<scope>): <imperative subject>

- <material effect or rationale>
- <material effect or verification-relevant behavior>
- <material effect when useful>

<optional footer>
```

Header rules:

- start the subject with an imperative verb
- do not end it with a period
- keep it concise, preferably within 50 characters
- omit empty parentheses when no scope is justified

Body rules:

- use 3 to 5 bullets when the diff contains that many meaningful points
- omit the body for a genuinely trivial atomic change rather than inventing
  filler or repeating the header
- keep bullets focused on intent, behavior, contracts, or important evidence
- keep lines within 72 characters when practical

Footer rules:

- add `BREAKING CHANGE:` only for a demonstrated incompatible contract
- add `Closes #<id>` or `Refs #<id>` only when the issue reference is supplied
  by the user, repository context, or staged change
- preserve required repository trailers without inventing identities

## Output modes

- `full` (default): header, meaningful body, and required footers
- `header-only`: one Conventional Commit header
- `alternatives`: two or three plausible messages for the same atomic change,
  only when explicitly requested

In pipeline mode, output no explanation, Markdown fence, label, or translation
outside the raw commit message. In standalone mode, add commentary only when
the user asks for it.

## Quality gate

Before returning the message, verify that it:

- describes the staged or supplied evidence rather than assumed intent
- represents one reason to change
- uses a repository-appropriate type and scope
- uses concrete language without filler, vague quality claims, or body/header
  repetition
- calls out a real breaking change and migration when present
- contains no unsupported issue, test, security, or compatibility claim

If the evidence cannot support a trustworthy message, report the missing or
mixed input instead of fabricating one.
