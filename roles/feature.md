---
name: multica-featssship-feature
description: Ship a delegated feature through one issue-owned Developer–Reviewer workflow with independent approval and verified integration.
---

Read the issue's request, scope, acceptance questions and configured agent IDs.
Use its shared repository checkout; run `multica repo checkout` only if absent.
From the repository root, run `python3 <this-skill-directory>/entry.py` and follow
its callbacks. Pass `--thread <trigger UUID>` on comment-triggered calls.

Developer owns `implement` and `integrate`: prepare, keep one feature commit,
amend corrections, submit with a concise `--summary`, then end the turn.
Reviewer owns `review`: inspect the submitted commit and diff without editing
source. Answer the acceptance, necessity and scope questions; approve or return
concrete findings, then end the turn. The script rejects the wrong agent ID.
Developer integrates only the approved revision; respect manual acceptance holds.
MAIN receives one verified result. Human acceptance owns done.

State belongs to the issue, shared by both agents. `--help` reads the latest
saved guidance without advancing. Follow errors, reconcile writes before retrying,
and use a returned `repaired` callback once for an assertion failure.
