---
name: multica-featssship-developer
description: Implement a delegated feature, correct independent review findings and integrate the approved revision.
---

As Developer, read the issue's request, scope and acceptance question. Check out
the configured repository with `multica repo checkout`. From its root, run
`python3 <this-skill-directory>/entry.py` and follow the callbacks. Pass
`--thread <trigger comment UUID>` on the first call for a comment-triggered task.

Prepare and implement the request. Keep one commit per feature; use
`git commit --amend` for corrections. Finish checks before submitting. Submit
with `--summary "<outcome; technical approach; necessary links or artifacts>"`.
The script reports line totals and the top three changed files and steers Reviewer.
End the turn after submission. Resume on Reviewer's reply and follow the returned
callback. Respect independent approval and manual holds; human acceptance owns done.
State and callback graphs: `DEBUG.md` in the installed package.
