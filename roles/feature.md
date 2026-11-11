---
name: multica-featssship-develop-review
description: Developer implements, tests and integrates; Reviewer only reads and returns a verdict in the same issue.
---

Use the prepared feature worktree named in the issue and MAIN's configured branch. Read its
request, scope and acceptance question, plus verification guidance in the project description. Run `python3 <this-skill-directory>/wrapper.py`.
Pass `--thread <trigger UUID>` on comment-triggered calls.
Start directly in `develop` on the issue's existing branch selected by MAIN.
Neither role names, creates, renames or switches branches, or makes another checkout.
The verdict checks that branch, repository and submitted HEAD
in place. A claimed short name is an error, never permission to overwrite another feature.

Developer implements one feature commit, amends corrections, tests and submits.
Reviewer only reads the exact submitted diff. Do not edit source, run tests,
merge or push. Answer the acceptance question and this issue's selected process questions
together in one `--finding`; approve or return corrections. Live review guidance
shows the selected questions and issue criteria.
For `manual: true`, Reviewer approval enters `manual_approve`. Exit silently until
superior instruction if outer confirmation has not been received yet. ONLY outer
allowed: a human or MAIN replies approve/rework/cancel to the review thread; Developer
executes that choice. Automated features skip this wait. No remote feature branch
is created or pushed unless manual.

Automated approval sends Developer to `approve`; manual approval waits in
`manual_approve`. Both approval choices call the same `merge_approved` action.
It verifies the approved HEAD, merges and advances local main before `finished`.
The declared merge-result diamond returns conflicts directly to develop for a
resolution merge commit and fresh review. Success automatically deletes the
owned local feature worktree/branch, pushes the integrated commit and reports to
MAIN as a receipt-only note in the original dispatch thread, without waking MAIN,
before entering terminal `finished`. There is no reported state or finish
command. Rejected pushes restore the feature worktree for rework.

`cancel` is available in develop, review and manual_approve (ONLY outer allowed).
Use it for wrong scope, incomplete Git/version infrastructure or refactoring
beyond the edit budget. Preserve or commit edits first. Cancellation performs
scripted local cleanup, marks the issue cancelled and enters finished without
integration, tests or pushing. Reviewer may invoke cancel cleanup, but never
perform source edits, tests or approved integration.

Rework returns only "Rework sent, directly and silently exit"; only Developer may
act in the resulting develop state. Other successful handoffs post one concise recipient
mention without a self-reference or SHA, then return only
"Delivery/review/work done this round, exit directly and silently".
Exit without commentary or another action. Already-reported calls
return the same instruction without another delivery. Receiver callbacks are not
sender instructions. This is guidance, not a runner-enforced stop. Failed
delivery remains an error. Wrong-role calls exit nonzero on stderr with no JSON
or state write.

Both roles share one issue metadata record. `--help` reads guidance without
advancing. Follow returned errors; reconcile writes before retrying. Use a
returned `repaired` callback once for an assertion failure.
