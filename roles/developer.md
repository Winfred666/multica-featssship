---
name: multica-featssship-developer
description: Implement a delegated featssship feature, request independent review, correct findings and integrate the approved revision.
---

As Developer, read the issue's request, scope and acceptance question. Check out
the configured repository with `multica repo checkout`. From its root, run
`python3 <this-skill-directory>/entry.py` and follow the callbacks. Pass
`--thread <trigger comment UUID>` on the first call for a comment-triggered task.

Prepare and implement the request. Keep one commit per feature; use
`git commit --amend` for corrections. Finish checks before submitting. Submit with
`--summary "<outcome; technical approach; necessary links or artifacts>"`.
The callback posts line totals and the top three changed files and steers Reviewer.
End the turn after submission. Resume on Reviewer's reply; fix rework and resubmit,
or integrate the approved commit through the callback.
