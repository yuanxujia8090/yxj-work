---
name: yxj-principle-build-the-lever
description: "Apply to any non-trivial work, not just bulk work: edits, migrations, analyses, checks. Build the tool that does it or proves it (codemod, script, generator, or a skill your subagents follow) instead of working by hand. The tool is the artifact a reviewer can rerun."
disable-model-invocation: true
---
# Build the Lever

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
create one. Never place workflow output in a project docs directory, in another skill's directory, in a
tool-specific hidden directory, or outside the repository. The full rule lives in `docs/file-boundary.md`
of the yxj-work source repository.

Files that are themselves the task target -- project code, project docs, existing config -- may be modified
in place. Record those paths in the contract and in `evidence/` before changing them, and do not copy them
into `.work-docs`. Before running any third-party skill that writes files, take a before/after inventory; a
write outside `.work-docs` that the contract did not authorize is a boundary violation: stop and report it.

When the work isn't trivial, build the tool that does it instead of doing it by hand.

**Why:** Two payoffs. Throughput: a codemod, generator, or script does the work the same way every time and reruns for free. Confidence: the tool is one artifact a reviewer can read and rerun to check the work. Hand-done changes can only be re-verified by redoing them. A deterministic script turns "trust me" into "run this".

**Pattern:** Default to building the lever. Skip it only when the task is trivial, a couple of obvious edits you can see at a glance.

- Do the first unit by hand to learn the recipe, then build the tool. Prove it by rerunning it on that unit and diffing against your hand-done version. Make the lever safe to rerun.
- Codemod or script for edits, generator for repetitive files, a dump-to-sqlite query for analysis, a rerunnable check for verification.
- A deterministic lever beats fan-out. If the tool can process every unit in one pass, run it yourself. Don't fan out delegates to hand-apply what a script can do.
- When you fan work out to subagents, write the lever as a skill they all read: the recipe, the verification contract, and the do-not-touch fences in one artifact. Keep it outside the delegates' write scope so they can't quietly edit the contract.
- Applying this principle produces a file. If you cited it and there is no codemod, script, generator, or delegate skill in the diff, you didn't apply it.
- Commit the lever when the work outlives the session.

**Balance:** The bar is triviality, not repetition. A one-off still earns a lever when the lever is what makes the work checkable. Per the [Laziness Protocol](../yxj-principle-laziness-protocol/SKILL.md), build the smallest script that does or proves the job, never a framework.

Distinct from [Encode Lessons in Structure](../yxj-principle-encode-lessons-in-structure/SKILL.md), which makes a recurring instruction a durable guardrail. This is throughput and reviewability on the work in front of you. For scripting the verification itself, see [Prove It Works](../yxj-principle-prove-it-works/SKILL.md).
