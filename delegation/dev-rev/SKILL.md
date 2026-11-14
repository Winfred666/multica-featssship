---
name: multica-featssship-develop-review
description: Developer implements and tests; Reviewer owns review, approved integration and completion.
metadata: {sop: symbolic}
---

Use this skill for delegated development and review. Developer implements and verifies;
Reviewer reviews and ships through the CLI callbacks.

Read the issue's request and scope, plus verification
guidance in the project description. Use the prepared issue worktree and MAIN-selected
branch without creating another checkout or switching branches.

From the target repository root, run `multica sop run multica-featssship-develop-review`.
The CLI discovers the repository-local skill.
Pass `--thread <trigger UUID>` on comment-triggered calls and follow the returned callback.

Keep one feature commit; amend corrections, never create merge commits. Reviewer
rebases onto latest main before integration. A changed revision needs a fresh
submission, review and any required outer approval. On REBASE CONFLICT, Developer
resolves and stages in the retained worktree, runs `git rebase --continue`, and
submits again.

Do not ask parent to arrange or authorize ordinary workflow transitions.

Posting comment to sibling or other outer issue must SEND extremely small and brief notices to original thread in MAIN issue for later audit. Never mention MAIN delegator in current sub-issue.

If a callback conflicts with a human restriction, report the exact incompatibility once and end the round; do not invent non-existent work process.
