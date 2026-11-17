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

Initial delivery uses configured approval. Amend shipped work only on an explicit
outer request: minimal inline replacements within that feature; reject another
feature. Amendment and recovery need no fresh review or approval.
