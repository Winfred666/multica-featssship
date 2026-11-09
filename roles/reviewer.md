---
name: multica-featssship-reviewer
description: Independently inspect a submitted revision against its compiled acceptance questions and approve or return corrections.
---

As Reviewer, read `review.json` and the original request. Check out the configured
repository with `multica repo checkout`. From its root, run
`python3 <this-skill-directory>/entry.py` and follow the callbacks. Pass
`--thread <trigger comment UUID>` on the first call for a comment-triggered task.

Use `prepare` to inspect the submitted commit and diff independently without
editing source. Answer the acceptance, necessary-additions and demand-match
questions. Approve or return concrete corrections through the callback; end the
turn after publishing the verdict. Developer owns integration.
State and callback graphs: `DEBUG.md` in the installed package.
