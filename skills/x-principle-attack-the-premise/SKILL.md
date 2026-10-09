---
name: x-principle-attack-the-premise
description: "Apply when two or more fixes that share one premise have failed the same gate. Take a census of which actors hold the imbalance before the next fix, then question the premise instead of writing another fix that assumes it."
disable-model-invocation: true
---

# Attack the Premise

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


When two or more fixes that share one premise have failed the same gate, suspect the premise, not the fixes.

**Why:** Each failure under a shared premise is evidence about the premise.

**Pattern:**
- **Write the premise down.** The premise is the one sentence that every failed fix assumed.
- **Take a census before the next fix.** Count the imbalance per actor. The census shows which actors hold the imbalance, not how large it is. Write the census as a rerunnable script per [Build the Lever](../x-principle-build-the-lever/SKILL.md).
- **Read the skew.** If the same few actors hold most of the imbalance on every run, something assigns them that role. Find what assigns the role. That assignment is the next "why" per [Fix Root Causes](../x-principle-fix-root-causes/SKILL.md).
- **Remove the asymmetry instead of compensating for it**, per the [Laziness Protocol](../x-principle-laziness-protocol/SKILL.md). Rotate the role between actors, randomize the assignment, or move the role, so that no actor holds it on every run. A return path, a shared pool, a batched hand-off, or a periodic rebalance leaves the assignment in place and adds work on every run.

**Stop:**
- Do not start the next fix before the premise is written down and the census exists.
- If the census is even across actors, the premise is not the cause. Look for the cause elsewhere and keep the census as evidence.

This principle is distinct from [Redesign from First Principles](../x-principle-redesign-from-first-principles/SKILL.md), which rebuilds a design around a new requirement. It questions a fact the current design assumes.
