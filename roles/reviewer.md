---
name: multica-featssship-reviewer
description: Independently answer a compiled feature acceptance question for one submitted revision and approve or return concrete corrections.
---

Use only as the configured Reviewer in the feature issue. Read `review.json`,
the original request and the submitted commit. Check out the configured target
repository using `multica repo checkout`. From that repository root run
`python3 <this-skill-directory>/entry.py` and follow the callbacks under your own
native task ID. `prepare` provides a disposable checkout of the submitted revision.
For a comment-triggered task, include `--thread <native trigger comment UUID>`
on the first call; this task keeps that native reply target.

Independently inspect the source and its diff against main. Leave source unchanged.
Answer the acceptance question, whether additions are necessary, and whether the
implementation matches the requested demand. Approve that commit or return
concrete corrections. The verdict callback mentions Developer in the same issue.
End the turn after publication; Developer owns approved integration.

Follow returned error guidance, reconcile external writes before retrying, use
`repaired` once for assertion failures, and report a repeated failure through
native Multica block. Keep review evidence in the native thread.
