---
name: multica-featssship
description: Draft a feature delegation, clarify one point at a time with the human, then dispatch a shared issue-owned Developer–Reviewer shipping flow.
---

Use in the installed MAIN DEV: issue. From the target repository root, run
`python3 <this-skill-directory>/wrapper.py` and follow its choices. On comment
triggers, pass `--thread <trigger UUID>` first.

Start directly in `grilling`, passing `--config '<JSON>'` with known request fields
on the first invocation. Config lives in MAIN issue metadata, not a local JSON
file or a comment. Use `edit --patch '<JSON merge patch>'` to
record changes. Ask one human question only when context leaves a field uncertain;
otherwise dispatch. If waiting for an outer reply, exit directly and silently if outer confirmation has not been received yet. Config and the child checkpoint remain after dispatch.
A new request uses a new `--thread` and `--config`; a retry reuses its existing child.

Give a short `name` such as `tree-horizontal-more`; the installed direction prefix
formats the branch, for example `feat/frontend/tree-horizontal-more`. `title` is optional. `manual` is a boolean, default false; only manual features publish a remote feature branch and wait for superior approval.

An optional GitHub URL is a source link for mirroring. Scope and
acceptance come from the delegation config. Never create GitHub issues
routinely. MAIN receives the final result and ends the turn when instructed.
Use `--help` to replay the saved decision, or read this body for a new/completed issue flow.
Installation: README.md.

In every state, follow returned error guidance and finish unmet prerequisites
before retrying. Reconcile writes first. For assertion failures, use the returned
`repaired` recall once; report a repeated failure through native Multica block.
