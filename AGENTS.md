# Developing multica-featssship

Read README.md for usage and [docs/workflow.md](docs/workflow.md) for source
layout and package builds. Keep procedure scripts in their owning SoP folder.
Use the CLI-owned Symbolic-SoP engine. Keep this repository atomic; no submodules.

Keep one commit per feature. Amend corrections and finish verification before pushing.

Declare global routing with native Workflow (source, destination) pairs and local action logic in short DOT docstrings. Reuse the RSI creator for protocol and renderer maintenance. Keep prompts limited to inputs, entry, judgment and exception handling. README covers installation and usage.

The first assigned prototype issue is explicitly authorized to develop and commit directly on `main`. It carries `dev` and `manual`; human review owns acceptance. Verify its repository and branch before editing. Report the prototype in its native issue and wait for human acceptance. Do not create a PR unless requested.

Installation is a resumable README-guided script in its assigned installer issue. It creates an independent MAIN DEV: issue, derives workspace/project from the installer, and separates agent edit, native outer_decide and retained finished states. Edit updates only the settings needed for the requested workflow, keeps choices that already fit, and allows repeated edits. Ask a human question only when context cannot resolve uncertainty. Outer questionnaire confirmation gates installation. Never search for a MAIN root or ask the human for an existing root UUID. Reuse the saved active MAIN/agent IDs on resumption. Root delegation is the only root SOP; Developer and Reviewer share one fixed feature skill; review questions resolve from the shared delegation. Build standalone repository-owned procedures and native Multica CLI actions. The product must not invoke system distribution, review or delivery SOP skills.

Developer and Reviewer have distinct native identities and separate contexts. Only develop belongs to Developer, who edits, tests and submits. All subsequent states belong to Reviewer, including approval, integration, push and completion. Retain one non-merge feature commit; amend corrections and continue any retained rebase. Reviewer reviews without editing source, returns corrections to Developer, and runs approved integration through the script. MAIN starts delegation in grilling with one issues-list batch document, refreshes it from an offline JSON file, waits for human confirmation, then dispatches and receives results. Preserve the original request, scope, selected review questions and review/rework loop.

Use `Workflow`, `State`, `Option` and declared prechecks from the current template. Each feature issue owns one SoP metadata record shared by both agents. Reject the wrong agent ID for the current phase. Dispatch prepares one issue-owned Git worktree; both roles use it without a separate Reviewer checkout. Let Git own worktree identity; store no custom folder registry or task ID. Publish findings, verdicts and delivery evidence as comments.

Keep tests under `tests/` small. Use real workspace runs for native handoffs and HTML verification instead of duplicating the platform or generic runtime's test suite. Reuse settled evidence; run only checks affected by a change. Keep workspace evidence outside Git.

MAIN passes a short feature name; the installed direction prefix formats its branch. Developer starts directly on the issue's existing named branch. Neither Developer nor Reviewer names, creates or switches branches. They retain that one branch and current issue folder through review and corrections; never check out a separate review branch. Review approval passes through the manual-config diamond; manual mode waits in manual_approve for outer approval. Both routes use the same registered final_approve action, then the integration-result diamond. Unsuccessful integration goes to Reviewer evaluation; only Reviewer-selected rework returns to develop. Preserve interrupted Git state. A clean rebase hash change alone retains approval and still runs required checks; Developer source corrections need fresh submission, review and any required outer approval. Success cleans the owned local worktree/branch, pushes to the remote parent and retains done for an explicit outer-requested amendment. Immediate completion reply guidance requests only silent exit; later done guidance states the feature is already pushed and offers amend. No reported state or finish command. Cancellation from develop, review or manual_approve cleans locally and enters finished without integration. Keep local configuration, generated packages, logs and credentials untracked. Preserve shared services and unrelated agents, skills, issues and data. Use ponytail and concise native replies.

## Implementation notes

Run affected local checks from `python3 -m unittest discover -s tests -v`.
Use the [RSI creator](https://github.com/Winfred666/multica-RSI/blob/main/harness/skills/create-symbolic-sop/scripts/check.py)
for generic runtime protocol and renderer checks, not another copy here.

Create MAIN without a parent, save its ID for same-cycle retries and subscribe CEO.
Preserve existing MAIN issues. Deploy skills only to the target repository.
Fixed script inputs come from JSON config; mutable execution checkpoints from issue metadata.
Issue/project titles and descriptions are display only.
Resolve settings through owner/filename references, never installation-parent ancestry.
Do not add nested-issue hierarchy or rubric-style tests. Publish tidy JSON to
enter the native outer questionnaire in the current installation issue/thread.
Keep change context with the attachment; return only silent final-hop guidance,
including initial publication. Outer confirms installation directly or requests
edits with one change-request argument; do not inspect confirmation comments.

The feature procedure stores one current record under
`issue.metadata["sop.multica-featssship-develop-review"]`; completion removes only
that key. `--help` must not advance state. Dispatch prepares a local feature branch/worktree; only manual mode reserves a remote branch.
Only manual submissions push the feature branch, leasing its base or prior submitted commit.
Preserve required checks without adding a global lock. See [docs/workflow.md](docs/workflow.md)
for routing, handoff output and debug graph behavior. Run procedures with
`multica sop run NAME`; `multica sop dev docs` describes the CLI-owned protocol.
