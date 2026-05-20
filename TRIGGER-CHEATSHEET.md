# Skill Trigger Cheatsheet

This is the fast "when should I use which skill?" reference for the installed Codex skill pack.

## Software Development

### `$guide`

Use when:

- you just entered an unfamiliar repo
- you want a quick briefing before doing anything
- local rules, commands, or conventions are unclear

Typical prompts:

- "Use `$guide` to summarize how this repo works."
- "What local workflow should we follow here?"
- "Before we start, brief me on the project rules."

### `$dev-loop`

Use when:

- you are implementing a feature or fix
- you are refactoring and need disciplined verification
- you want a clear done-state with what was tested and what was skipped

Typical prompts:

- "Use `$dev-loop` to implement this bug fix and verify it."
- "Add this feature and make sure the important checks run."
- "Refactor this module and report residual risk."

### `$north-star`

Use when:

- project priorities are vague
- you need measurable targets before optimizing
- multiple approaches are valid and you need tradeoff criteria

Typical prompts:

- "Use `$north-star` to define what this project should optimize for."
- "What 1-3 metrics actually matter here?"
- "Help me set concrete targets before we refactor further."

### `$long-horizon`

Use when:

- you want Codex to interrupt less
- the task will run for a while with many small decisions
- you want explicit escalation rules instead of constant questions

Typical prompts:

- "Use `$long-horizon` and just keep moving unless you hit a real decision point."
- "Work autonomously and batch questions."
- "Handle the low-level choices yourself and escalate only when needed."

### `$new-project`

Use when:

- starting a greenfield repo or subsystem
- you need to scope the first useful slice
- you want to set up requirements and structure before coding

Typical prompts:

- "Use `$new-project` to scaffold the first version of this tool."
- "Start this subsystem from scratch with a minimal but solid structure."
- "Help define the first slice and repo layout."

### `$existing-project`

Use when:

- taking over a legacy or unfamiliar codebase
- you need to reconstruct intent before changing behavior
- docs, tests, and code may disagree

Typical prompts:

- "Use `$existing-project` to map this repo before we touch anything."
- "Help me figure out how this old service actually works."
- "Recover the important modules and conflicts first."

## Research

### `$research-ideation`

Use when:

- you have a research hunch but not a testable hypothesis
- you are considering a pivot
- you need quick validation criteria before formal experiments

Typical prompts:

- "Use `$research-ideation` to turn this idea into a testable hypothesis."
- "Help me refine this research direction."
- "What would make this idea falsifiable?"

### `$experiment-lab`

Use when:

- planning or running experiments
- organizing baselines, ablations, and result comparisons
- you need traceable run records

Typical prompts:

- "Use `$experiment-lab` to design this ablation study."
- "Track these experiment runs and compare them properly."
- "Help structure the experiment plan and outputs."

### `$paper-craft`

Use when:

- drafting or polishing a paper in LaTeX
- aligning claims with evidence and figures
- handling revision, rebuttal, or camera-ready checks

Typical prompts:

- "Use `$paper-craft` to turn these results into a paper section."
- "Polish this paper draft and check claim-evidence consistency."
- "Help prepare the rebuttal changes cleanly."

### `$research-comm`

Use when:

- preparing an advisor update
- deciding what to discuss in a meeting
- compressing experiment progress into a few important points

Typical prompts:

- "Use `$research-comm` to prepare for tomorrow's advisor meeting."
- "What are the 3-5 discussion points that matter?"
- "Turn these logs into a focused research update."

### `$talk-architect`

Use when:

- turning a paper or notes into a talk outline
- the story, audience framing, or pacing is not stable yet
- you need slide-by-slide planning before deck implementation

Typical prompts:

- "Use `$talk-architect` to build a seminar outline from this paper."
- "Plan a 20-minute conference talk from these materials."
- "Help me compress this work into a clear talk story."

### `$slidecraft`

Use when:

- building or revising an academic deck
- fixing layout, density, reveal logic, or visual-system issues
- implementing slides from an already-known talk plan

Typical prompts:

- "Use `$slidecraft` to build this academic deck."
- "Fix the slide density and layout problems."
- "Implement these planned slides with a consistent visual system."

### `$plotting`

Use when:

- making publication-quality figures
- choosing chart form for a research claim
- improving figure readability, labels, or uncertainty display

Typical prompts:

- "Use `$plotting` to design a figure for this experiment result."
- "What is the right chart for this comparison?"
- "Clean up this paper figure and make it publication-ready."

### `$pptx`

Use when:

- the source of truth is an actual `.pptx` file
- you need deck extraction, merging, splitting, or artifact QA
- you are editing a template or native PowerPoint asset directly

Typical prompts:

- "Use `$pptx` to inspect and clean up this deck."
- "Extract the text from this PowerPoint and summarize it."
- "Merge these PPTX files and run final QA."

## Reporting

### `$weekly-report`

Use when:

- you want a weekly summary from commit history
- you need a report that merges noisy commits into real outcomes
- you want a Chinese or English work summary quickly

Typical prompts:

- "Use `$weekly-report` to summarize this week's work."
- "Generate a weekly report from my recent commits."
- "Turn the last 7 days of git history into a concise update."

## Simple Routing Rules

- Unknown repo first: `$guide`
- Coding work in progress: `$dev-loop`
- Need goals before action: `$north-star`
- Want more autonomy: `$long-horizon`
- New repo: `$new-project`
- Old repo: `$existing-project`
- Research idea: `$research-ideation`
- Research experiment: `$experiment-lab`
- Writing paper: `$paper-craft`
- Preparing meeting update: `$research-comm`
- Planning talk: `$talk-architect`
- Building slides: `$slidecraft`
- Making figures: `$plotting`
- Editing a real PowerPoint artifact: `$pptx`
- Writing weekly update: `$weekly-report`
