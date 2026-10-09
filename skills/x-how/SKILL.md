---
name: x-how
description: "Use for \"how does X work\", code walkthroughs before changing something, and placement / ownership / layering questions (\"where should this live\", \"which package owns this\", \"is this the right layer\"). Explains subsystem architecture, runtime flow, onboarding mental models. Use why for motivation."
disable-model-invocation: true
---

# How

## File boundary

The workflow root is the directory this skill runs in (`<execution-root>`). Every durable file this skill
generates goes under:

```text
<execution-root>/.work-docs/tasks/<task-id>/
├── contract.md   what done means, allowed changes, verification layers
├── state.md      stage, status, evidence pointers, blockers
├── outputs/      final reports, designs, plans, manuals
├── evidence/     command output, measurements, failure evidence
├── audit/        decisions, checkpoints, work-in-progress records
└── tmp/          fixtures and disposable material
```

Reuse the task id already in progress when the scope matches (read `.work-docs/index.md` first), otherwise
allocate one: `{YYYYMMDD}-{NN}-{slug}`, where `NN` is a two-digit per-day counter that
restarts at `01` and never reuses a retired number, then append the new task to `.work-docs/index.md`.
Never place workflow output in a project docs directory, in another skill's directory, in a
tool-specific hidden directory, or outside the repository.

Files that are themselves the task target -- project code, project docs, existing config -- may be modified
in place. Record those paths in the contract and in `evidence/` before changing them, and do not copy them
into `.work-docs`. Before running any third-party skill that writes files, take a before/after inventory; a
write outside `.work-docs` that the contract did not authorize is a boundary violation: stop and report it.

## External dependencies

No external model-routing file is required. Use the current session's model for every role this skill names,
and keep reviewer/runner counts at their defaults.



Explore the codebase to answer "how does X work?" questions. Produce architectural explanations at the level of a senior engineer onboarding onto a subsystem, enough to build a working mental model, not so much that it reads like annotated source code.

Each spawn below names a role. Use the current session's model for it. Leave `model` unset when the role says `inherit-parent`. If the Task tool rejects a slug, use the closest valid slug of the same family from its error message and say so.

## Step 1. Assess Complexity

If the scope is ambiguous, state your interpretation and explore. The user can redirect.

- **Simple** (a single module, a small utility, a narrow question such as "how does function X work"): no explorers. One explainer explores and explains in a single pass. Go to Step 2b.
- **Complex** (a subsystem spanning multiple files or services, a cross-cutting feature, a full architectural overview): spawn parallel explorers first, then hand off to the explainer. Go to Step 2a.

When in doubt, take the simple path.

## Step 2a. Explore (complex questions only)

Decompose the question into 2 to 4 exploration angles, each a distinct slice of the subsystem. Spawn all explorers in a single message:

- `subagent_type`: `generalPurpose`
- `model`: omit to run on the parent (current session) model
- `readonly`: `true`

Each explorer gets the prompt in `references/explorer-prompt.md` with its angle filled in. Then go to Step 3.

## Step 2b. Direct Explain (simple questions)

Spawn one Task subagent that explores and explains in one pass:

- `subagent_type`: `generalPurpose`
- `model`: omit to run on the parent (current session) model
- `readonly`: `true`

Build its prompt from `references/explainer-prompt.md` without the explorer-findings section. Go to Step 4.

## Step 3. Synthesize (complex questions only)

Once all explorers have returned, spawn one Task subagent to synthesize their findings into one explanation:

- `subagent_type`: `generalPurpose`
- `model`: omit to run on the parent (current session) model
- `readonly`: `true`

Build its prompt from `references/explainer-prompt.md` with every explorer's findings filled in.

## Step 4. Present

Present the explainer's output to the user. Light edits for clarity or context from the conversation are fine. Do not substantially rewrite it.

## Output Format

The explanation uses the sections defined in `references/explainer-prompt.md`, dropping any that do not apply: Overview, Key Concepts, How It Works, Where Things Live, Gotchas.
