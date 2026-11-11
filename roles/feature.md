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

Approval sends Developer to `finished`, not a separate integration stage.
The `finish` action verifies the approved HEAD, integrates, automatically removes
the owned local branch/worktree, pushes the integrated commit to the remote parent,
and reports to MAIN. Merge conflicts return directly to develop for a resolution
merge commit and another review; rejected parent pushes restore the worktree
for rework. Other failures preserve the worktree and report the problem. Manual mode uses the same cleanup
because superior approval already happened. `cancel` is also available in develop
(for wrong scope, incomplete Git/version infrastructure, or refactoring beyond the
allowed edit budget) and manual_approve (ONLY outer allowed). Preserve or commit
edits first. Cancellation marks the issue cancelled, then finished deletes the
local worktree/branch without testing, merging or pushing the feature.

Rework returns only "Rework sent, directly and silently exit"; only Developer may
act in the resulting develop state. Other successful handoffs post one recipient TODO with a
result link, then return only "Delivery/review/work done this round, exit directly
and silently". Exit without commentary or another action. Already-reported calls
return the same instruction without another delivery. Receiver callbacks are not
sender instructions. This is guidance, not a runner-enforced stop. Failed
delivery remains an error. Wrong-role calls exit nonzero on stderr with no JSON
or state write.

Both roles share one issue metadata record. `--help` reads guidance without
advancing. Follow returned errors; reconcile writes before retrying. Use a
returned `repaired` callback once for an assertion failure.
