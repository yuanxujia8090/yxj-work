# Investigate Playbook

1. Read task state, contract and recent evidence before broad exploration.
2. State the observable question and done_when; identify the smallest read or runtime check that can answer it.
3. Narrow files, configuration, services and versions before running commands.
4. Record findings as fact, inference or unknown with evidence pointers.
5. Report the affected verification layer: `syntax/config`, `static`, `runtime/local`, `external`, or `consumer`.
6. Do not create a formal output unless the contract requires one; durable command results belong in `evidence/` and decisions in `audit/`.
7. If evidence cannot resolve the question, set `blocked` with attempted paths, shared assumption, unblock condition and next action.
