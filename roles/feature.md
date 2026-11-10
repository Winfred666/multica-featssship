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

Successful submit, verdict and parent reporting post one recipient TODO with a
result link, then return only "Delivery/review/work done this round, exit directly
and silently". Exit without commentary or another action. Already-reported calls
return the same instruction without another delivery. Receiver callbacks are not
sender instructions. This is guidance, not a runner-enforced stop. Failed
delivery remains an error. Wrong-role calls exit nonzero on stderr with no JSON
or state write.

Both roles share one issue metadata record. `--help` reads guidance without
advancing. Follow returned errors; reconcile writes before retrying. Use a
returned `repaired` callback once for an assertion failure.
