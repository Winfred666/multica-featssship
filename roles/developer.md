---
name: multica-featssship-developer
description: Implement a delegated featssship feature, request independent review, correct findings and integrate the approved revision.
---

Use in the feature issue as its configured Developer and workflow owner. Read the
request, scope and acceptance question from the native issue. Check out its
configured repository using `multica repo checkout`, then from that repository
root run `python3 <this-skill-directory>/entry.py` and follow its callbacks.
For a comment-triggered task, include `--thread <native trigger comment UUID>`
on the first call; this task keeps that native reply target.

Prepare the feature branch, implement the request and commit. Submit with the
acceptance answer and a concise explanation. The callback tests and pushes the
commit, compiles the independent Reviewer's question package and mentions it.
End the turn while awaiting its native reply. Resume under your own task ID;
correct returned findings and submit for fresh review. After approval, the
integration callback merges, verifies and pushes, then sends MAIN one result.
Preserve manual holds and leave done to the human. MAIN only dispatches and receives.

Follow returned error guidance, reconcile external writes before retrying, use
`repaired` once for assertion failures, and report a repeated failure through
native Multica block. After an uncertain comment write, inspect the native thread
before retrying. Review and delivery records stay in comments.
