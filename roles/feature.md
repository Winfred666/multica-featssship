---
name: multica-featssship-develop-review
description: Developer implements, tests and integrates; Reviewer only reads and returns a verdict in the same issue.
---

Use the issue's current folder and MAIN's configured feature branch. Read its
request, scope and acceptance question. Run `python3 <this-skill-directory>/wrapper.py`.
Pass `--thread <trigger UUID>` on comment-triggered calls.
Start directly in `develop` on the issue's existing branch selected by MAIN.
Neither role names, creates, renames or switches branches, or makes another checkout.
The verdict checks that branch, repository and submitted HEAD
in place. A claimed short name is an error, never permission to overwrite another feature.

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
