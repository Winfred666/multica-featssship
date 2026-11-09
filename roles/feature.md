---
name: multica-featssship-develop-review
description: One issue workflow shared by Developer and Reviewer; develop, review, then merge or report manual handling to MAIN.
---

Use the issue's current folder and feature branch supplied by MAIN. Read its
request, scope and acceptance question. Run `python3 <this-skill-directory>/wrapper.py`.
Pass `--thread <trigger UUID>` on comment-triggered calls.

Developer implements one feature commit, amends corrections, tests and submits.
Reviewer inspects the exact submitted diff without editing code. Answer the
acceptance question and assess necessity and scope in `--finding`. Return
corrections, or approve to merge and test. A manual label, conflict or failed
integration sends a note to MAIN and finishes. End the turn after a handoff.
The script rejects the wrong native agent ID for the current phase.

Both roles share one issue metadata record. `--help` reads guidance without
advancing. Follow returned errors; reconcile writes before retrying. Use a
returned `repaired` callback once for an assertion failure.
