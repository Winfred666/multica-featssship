---
name: multica-featssship-develop-review
description: Developer implements, tests and integrates; Reviewer only reads and returns a verdict in the same issue.
---

Use the issue's current folder and feature branch supplied by MAIN. Read its
request, scope and acceptance question. Run `python3 <this-skill-directory>/wrapper.py`.
Pass `--thread <trigger UUID>` on comment-triggered calls.
Both agents use that same folder and branch; do not create a review checkout or
switch branches. The verdict checks the shared tree and submitted HEAD in place.

Developer implements one feature commit, amends corrections, tests and submits.
Reviewer only reads the exact submitted diff. Do not edit source, run tests,
merge or push. Answer the acceptance question and both default review questions
together in one `--finding`; approve or return corrections. The HTML review node
shows the defaults and live review guidance includes the issue's criteria.
Approval returns integration to Developer. Developer verifies the approved HEAD,
tests, integrates and reports to MAIN. A manual label, conflict or failed
integration sends a note to MAIN and finishes.

Handoffs return a plain stop message to the sender, not the next role's guidance.
End the turn. Wrong-role calls exit nonzero on stderr with no JSON or state write.

Both roles share one issue metadata record. `--help` reads guidance without
advancing. Follow returned errors; reconcile writes before retrying. Use a
returned `repaired` callback once for an assertion failure.
