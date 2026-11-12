---
name: multica-featssship-develop-review
description: Developer implements and tests; Reviewer owns review, approved integration and completion.
---

Use the prepared feature worktree named in the issue and MAIN's configured branch. Read its
request, scope and acceptance question, plus verification guidance in the project description. Run `python3 <this-skill-directory>/wrapper.py`.
Pass `--thread <trigger UUID>` on comment-triggered calls.
Start directly in `develop` on the issue's existing branch selected by MAIN.
Neither role names, creates, renames or switches branches, or makes another checkout.
The verdict checks that branch, repository and submitted HEAD
in place. A claimed short name is an error, never permission to overwrite another feature.

Developer owns `develop` and `amending`; Reviewer owns review, approval and retained
`done`. In develop, implement one feature commit, amend corrections, test and submit.
In `review`, read the exact submitted diff without source edits or tests. Answer
acceptance and process questions together in one `--finding`; approve or rework.
Reviewer can return corrections from review or manual_approve; only Developer implements.
Automatic approval continues to `approve` with the same Reviewer. With
`manual: true`, wait in `manual_approve` for a human or MAIN to instruct
approve/cancel in the review thread. Directly and silently end this turn. Reviewer executes that choice.
Only manual submissions push a remote feature branch.

Both approval states use `final_approve` to run `merge_approved`: verify the approved HEAD, merge/test,
advance local main, clean up, push and leave MAIN a native `/note` in the
original dispatch thread without mentions or waking MAIN. The receipt is marked as
that thread’s solution. Conflicts or rejected integration pushes return to Developer
in `develop` for a resolution merge commit and fresh review. The `merge_result` branch
has outcomes `rework` → develop and `merged` → done; outcomes are not states or options.
There is no reported state or finish command. Source edits belong only in develop or amending.

`done` is retained, not terminal completion. Ordinary entry says directly and silently
end this turn, without repeating delivery or removing SoP state. Only an explicit
human or MAIN request allows Reviewer to run `amend --thread <request UUID>` from
the target repository root. It recreates the issue checkout on the same branch at
the delivered commit, marks the native issue in_progress and hands it to Developer
in `amending`. Amend that commit in place with `git commit --amend`; interact briefly
with outer as needed. Do not submit or start a review loop. Run `push` from the
recreated issue checkout to reuse publication and cleanup, mark the native issue
done and retain done again. The amended parent push leases the delivered commit;
a rejected push restores the checkout and stays amending for outer resolution.

`cancel` is available in develop, review and manual_approve (ONLY outer allowed).
Use it for wrong scope, incomplete Git/version infrastructure or refactoring
beyond the edit budget. Preserve or commit edits first. Cancellation performs
scripted local cleanup, marks the issue cancelled and enters the built-in `finished`
completion (`Workflow.FINISHED`), which removes SoP state. It does not integrate,
test or push. There is no custom finished state; wrapper completion semantics stay unchanged.

Rework returns only "Rework sent, directly and silently end this turn"; only Developer may
act in the resulting develop state. Other successful handoffs post one concise recipient
mention without a self-reference or SHA, then return only
"Delivery done this round, directly and silently end this turn".
End this turn without commentary or another action. Already-reported calls
return the same instruction without another delivery. Receiver callbacks are not
sender instructions. This is guidance, not a runner-enforced stop. Failed
delivery remains an error. Wrong-role calls exit nonzero on stderr with no JSON
or state write.

Both roles read the same dispatch-authored delegation attachment through
`featssship.delegation`; never create or copy a config. Configuration access
needs only the explicit owner/filename reference, not installer ancestry.
Both roles share one execution metadata record. `--help` reads guidance without
advancing. Follow returned errors; reconcile writes before retrying. Use a
returned `repaired` callback once for an assertion failure.
