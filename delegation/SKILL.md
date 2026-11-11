---
name: multica-featssship
description: Draft a feature delegation, clarify one point at a time with the human, then dispatch a shared issue-owned Developer–Reviewer shipping flow.
---

Use in the installed MAIN DEV: issue. From the target repository root, run
`python3 <this-skill-directory>/wrapper.py` and follow its choices. On comment
triggers, pass `--thread <trigger UUID>` first.

Start directly in `grilling`, passing `--config '<JSON>'` with known request fields
on the first invocation. The installer-owned master is linked by `featssship.config`; request settings
live in a derived JSON attachment linked by `featssship.delegation`. Read the
referenced owner issue, download its latest attachment with that filename, and
read the JSON. Metadata never stores settings. Use `edit --patch '<JSON merge patch>'` to
record changes. Ask one human question only when context leaves a field uncertain;
otherwise dispatch. If waiting for an outer reply, exit directly and silently if outer confirmation has not been received yet. The document reference and child checkpoint remain after dispatch.
A new request uses a new `--thread` and `--config`; a retry reuses its existing child.

Give a short `name` such as `tree-horizontal-more`; the installed direction prefix
formats the branch, for example `feat/frontend/tree-horizontal-more`. `title` is optional. `manual` is a boolean, default false; only manual features publish a remote feature branch and wait for superior approval.

An optional GitHub URL is a source link for mirroring. Scope and
acceptance come from the delegation config. Reuse a supplied GitHub issue.
Proactively create one only for a valuable or impressive feature after the user
explicitly approves its creation during delegation; set `github_issue` in the
delegation config to its URL. Never create feature issues for trivial fixtures or
very minor features. MAIN receives the final result and ends the turn when instructed.
Use `--help` to replay the saved decision, or read this body for a new/completed issue flow.
Installation: the featssship source README and `installation/wrapper.py`.

In every state, follow returned error guidance and finish unmet prerequisites
before retrying. Reconcile writes first. For assertion failures, use the returned
`repaired` recall once; report a repeated failure through native Multica block.
