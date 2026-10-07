# Investigate Playbook

1. For a new formal task, create the task skeleton and minimal contract, then run `skills/yxj-work/scripts/check-contract.sh <task-dir>` before broad exploration. For an existing task, read task state, contract and recent evidence first. If a model request times out, record a recovery summary in `audit/` before continuing.
2. State the observable question and done_when; identify the smallest read or runtime check that can answer it.
3. Narrow files, configuration, services and versions before running commands.
4. Record findings as fact, inference or unknown with evidence pointers.
5. Report the affected verification layer: `syntax/config`, `static`, `runtime/local`, `external`, or `consumer`.
6. Do not create a formal output unless the contract requires one; durable command results belong in `evidence/` and decisions in `audit/`.
7. If evidence cannot resolve the question, set `blocked` with attempted paths, shared assumption, unblock condition and next action.
