---
name: multica-featssship-develop-review
description: Developer implements and tests; Reviewer owns review, approved integration and completion.
metadata: {sop: symbolic}
---

Use this skill for delegated development and review. Developer implements and verifies;
Reviewer reviews and ships through the CLI callbacks.

Read the issue's request, selected scope and verification command. Use the prepared
issue worktree and MAIN-selected branch without creating another checkout or switching branches.

From the target repository root, run `multica sop run multica-featssship-develop-review`.
The CLI discovers the repository-local skill.
Pass `--thread <trigger UUID>` on comment-triggered calls and follow the returned callback.

Keep one feature commit; amend corrections, never create merge commits. Reviewer
rebases onto latest main before integration and owns integration/publication recovery,
including conflicts and main advancing. A clean rebase hash change alone is not source
rework. Preserve required checks and actual review/approval gates. Only Reviewer choosing
rework returns to Developer, who resolves any retained rebase, tests and submits again.

Follow `this_round_reply_guidance` for direct handoffs: use
`multica-peer-mention-protocol` to mention the receiving role in the current issue
thread. Reuse the supplied mention, revision, diff facts and links; fill only the
brief semantic placeholder from the actual changes. Largest-file counts are not
the complete feature explanation. Do not craft special comments or steer runs.
Then end the turn silently. Do not run that role’s callback.
Automatic approval continues through integration; manual approval still waits
for a human or MAIN instruction in `manual_approve`.

Do not ask parent to arrange or authorize ordinary workflow transitions.

Posting comment to sibling or other outer issue must SEND extremely small and brief notices to original thread in MAIN issue for later audit. Never mention MAIN delegator in current sub-issue.

If a callback conflicts with a human restriction, report the exact incompatibility once and end the round; do not invent non-existent work process.
