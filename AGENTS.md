# Developing multica-featssship

Read README.md and docs/workflow.md. Source SoPs live in `installation/`,
`delegation/` and `delegation/dev-rev/`. Keep procedure scripts and runtime files
inside these folders. Build the smallest complete Developer–Reviewer prototype
using the bundled Symbolic-SoP runtime. Keep this repository atomic; do not add
submodules.

Keep one commit per feature. Amend corrections and finish verification before pushing.

Declare global routing in Workflow and local action logic in short DOT docstrings. Reuse the RSI creator for protocol and renderer maintenance. Keep prompts limited to inputs, entry, judgment and exception handling. README covers installation and usage.

The first assigned prototype issue is explicitly authorized to develop and commit directly on `main`. It carries `dev` and `manual`; human review owns acceptance. Verify its repository and branch before editing. Report the prototype in its native issue and wait for human acceptance. Do not create a PR unless requested.

Installation is a resumable README-guided script in its assigned installer issue. It creates an independent MAIN DEV: issue, derives workspace/project from the installer, and uses only grilling and finished states. Grilling updates only the settings needed for the requested workflow, keeps choices that already fit, and allows repeated edits. Ask a human question only when context cannot resolve uncertainty. Human confirmation gates all installation writes. Never search for a MAIN root or ask the human for an existing root UUID. Reuse the saved active MAIN/agent IDs on resumption. Root delegation is the only root SOP; Developer and Reviewer share one fixed feature skill; acceptance questions come from their issue. Build standalone repository-owned procedures and native Multica CLI actions. The product must not invoke system distribution, review or delivery SOP skills.

Developer and Reviewer have distinct native identities and separate contexts. Only develop belongs to Developer, who edits, tests and submits. All subsequent states belong to Reviewer, including approval, integration, push and completion. Retain one non-merge feature commit; allow a merge-resolution commit when parent integration returns rework. Reviewer reviews without editing source, returns corrections to Developer, and runs approved integration through the script. MAIN starts delegation in grilling with one issues-list batch document, refreshes it from an offline JSON file, waits for human confirmation, then dispatches and receives results. Keep settings in the installer-owned master JSON and dispatch-derived delegation attachments. Metadata stores only their references and necessary execution checkpoints. Preserve the original request, acceptance question, functional review questions and review/rework loop.

Runtime and common helpers live once in `installation/`; the builder includes them in every standalone package.

Use `Workflow`, `State`, `Option` and declared prechecks from the current template. Each feature issue owns one SoP metadata record shared by both agents. Reject the wrong agent ID for the current phase. Dispatch prepares one issue-owned Git worktree; both roles use it without a separate Reviewer checkout. Let Git own worktree identity; store no custom folder registry or task ID. Publish findings, verdicts and delivery evidence as comments.

Keep tests under `tests/` small: installer resumption, delegation, branch/routing guards and one correction/integration smoke path. Use real workspace runs for native handoffs and HTML verification instead of duplicating the platform or generic runtime's test suite. Reuse settled evidence; run only checks affected by a change. Keep workspace evidence outside Git.

MAIN passes a short feature name; the installed direction prefix formats its branch. Developer starts directly on the issue's existing named branch. Neither Developer nor Reviewer names, creates or switches branches. They retain that one branch and current issue folder through review and corrections; never check out a separate review branch. Manual review approval waits in manual_approve for outer approval; Reviewer may return corrections directly. Otherwise Reviewer continues to approve. Both approve and manual_approve call the same merge action before the declared conflict diamond: rework returns to develop; success deletes the owned local worktree/branch, pushes to the remote parent and enters terminal finished. No reported state or finish command. Cancellation from develop, review or manual_approve cleans locally and enters finished without integration. Keep local configuration, generated packages, logs and credentials untracked. Preserve shared services and unrelated agents, skills, issues and data. Use ponytail and concise native replies.

## Implementation notes

Run local checks with `python3 -m unittest discover -s tests -v`. Build packages
from `installation/` with `packages.build('installation', ...)`,
`packages.build('delegation', ...)` or `packages.build('feature', ...)`; each
validates via its `wrapper.py --validate`.
Use the [RSI creator](https://github.com/Winfred666/multica-RSI/blob/main/harness/skills/create-symbolic-sop/scripts/check.py)
for generic runtime protocol and renderer checks, not another copy here.

Create MAIN without a parent, save its ID for same-cycle retries and subscribe CEO.
Preserve existing MAIN issues. Bind skills additively. The installer-owned
`featssship-config.json` is the settings source: no local answers, cached config
or binding JSON. MAIN links the master, then derives a delegation containing only request overrides.
Dev-rev reads that document and resolves universal settings from its master reference. Keep reusable installed agent/skill IDs
in the master and execution checkpoints in metadata. Resolve settings through
owner/filename references, never installation-parent ancestry. Do not add nested-issue hierarchy
or rubric-style tests; keep verification focused on functional shipping behavior. Project context may include
repository/scope/tests, never review questions or installed IDs. After edit, attach
tidy JSON, ask the human to edit or confirm, and tell the agent to directly and silently end this turn if outer confirmation has not been received yet.

The feature procedure stores one current record under
`issue.metadata["sop.multica-featssship-develop-review"]`; completion removes only
that key. `--help` must not advance state. Dispatch prepares a local feature branch/worktree; only manual mode reserves a remote branch.
Only manual submissions push the feature branch, leasing its base or prior submitted commit.
Verification commands come from the project description, not delegation config. Preserve
these checks without adding a global lock. See [docs/workflow.md](docs/workflow.md)
for routing, handoff output and debug graph behavior. The accepted runtime
protocol is [RSI 0fd1fbb4a](https://github.com/Winfred666/multica-RSI/commit/0fd1fbb4a).
