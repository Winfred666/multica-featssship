---
name: multica-featssship-develop-review
description: Implement, review and submit a delegated feature.
metadata: {sop: symbolic}
---

Inputs: the delegated issue's request, scope and verification command.

From the prepared issue worktree on MAIN's selected branch, run
`multica sop run multica-featssship-develop-review`.

Keep one feature commit; amend corrections without switching branches.
Before submit, inspect pending main product changes and pass a meaningful
`--main-subject`, usually `simplify(<scope>): <change>`, when main needs a commit.
For submit and amendment push, pass `--changes` as a JSON object mapping each of
the three largest changed file paths to a short behavior explanation for the
delivery table. Parent completion forwards the same explained diff after integration.
Submission commits product edits without private/local paths,
pushes main including local commits, then rebases and checks the feature before review. Keep credentials
and generated/local paths ignored; never put private data in product files.
Reviewer recovers clean Git failures with `environment_repaired`. Human working
edits on main are stashed while main advances, then restored. Restore conflicts
stay on main with the stash retained and reported; feature delivery continues.
If upstream advances after a rejected push, recovery verifies both revisions,
publishes the rebased feature directly and leaves conflicted local main untouched.
Main working edits do not require Developer resubmission.
A completed rebase without a checkpoint must match the clean replay of the
approved commit onto main; keep the original approval revision. Only corrections
to the feature require resubmission, review and configured outer approval.
Recovery before review cannot bypass configured feature approval.

Follow the returned choices and reply guidance. Post any requested handoff,
then end the turn without running the receiving role's callback.

Initial delivery uses configured approval. Amend shipped work only on an explicit
outer request in the forwarded completion card: minimal inline replacements
within that feature; reject another feature. Amendment and recovery need no fresh review or approval.
