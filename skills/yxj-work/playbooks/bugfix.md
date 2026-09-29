# Bugfix Playbook

0. Verify the working context before reproducing: execution root, branch/worktree, and whether the issue is already fixed there (`git log -S`, `git branch --contains`, current diff). Record workspace facts in the contract. If the report does not match the current baseline, stop and confirm the target workspace with the user.
1. Reproduce with expected versus actual behavior; prefer a failing command or behavioral test.
2. If reproduction fails, record attempted paths and stop guessing.
3. Identify the root cause and the invalid assumption with file/log evidence.
4. Make the smallest root-cause fix; label symptom-only mitigation explicitly.
5. Re-run the original reproduction surface and relevant existing checks.
6. After three consecutive required verification failures, stop modifications, record strategy fingerprints and revalidate the shared assumption.
7. Preserve failing-before and passing-after evidence. The task cannot be done without both when reproducible.
