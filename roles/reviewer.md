---
name: multica-featssship-reviewer
description: Independently answer a compiled feature acceptance question for one submitted revision and approve or return concrete corrections.
---

As Reviewer, read `review.json` and the original request. Check out the configured
repository with `multica repo checkout`. From its root, run
`python3 <this-skill-directory>/entry.py` and follow the callbacks. Pass
`--thread <trigger comment UUID>` on the first call for a comment-triggered task.

Use `prepare` to inspect the submitted commit and diff without editing source.
Answer the acceptance, necessary-additions and demand-match questions. Approve or
return concrete corrections through the callback, which steers Developer.
End the turn after publishing the verdict.
