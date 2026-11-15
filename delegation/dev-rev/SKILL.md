---
name: multica-featssship-develop-review
description: Implement, review and submit a delegated feature.
metadata: {sop: symbolic}
---

Inputs: the delegated issue's request, scope and verification command.

From the prepared issue worktree on MAIN's selected branch, run
`multica sop run multica-featssship-develop-review`.
Pass `--thread <trigger UUID>` on comment-triggered calls.

Keep one feature commit; amend corrections without switching branches.
Follow the returned choices and reply guidance. Post any requested handoff,
then end the turn without running the receiving role's callback.

Wait for outer approval when requested. Amend shipped work only on an explicit
outer request. If a callback conflicts with a human restriction, report it and stop.
