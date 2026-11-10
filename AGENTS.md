# Developing multica-featssship

Read README.md and docs/workflow.md. Build the smallest complete Developer–Reviewer prototype using the bundled Symbolic-SoP runtime. Keep this repository atomic; do not add submodules.

Keep one commit per feature. Amend corrections and finish verification before pushing.

Declare global routing in Workflow and local action logic in short DOT docstrings. Reuse the RSI creator for protocol and renderer maintenance. Keep prompts limited to inputs, entry, judgment and exception handling. README covers installation and usage.

The first assigned prototype issue is explicitly authorized to develop and commit directly on `main`. It carries `dev` and `manual`; human review owns acceptance. Verify its repository and branch before editing. Report the prototype in its native issue and wait for human acceptance. Do not create a PR unless requested.

Installation is a resumable README-guided script in its assigned installer issue. It creates its own MAIN DEV: child, derives workspace/project from the installer, and returns one self-contained unanswered question per invocation. Never search for a MAIN root or ask the human for an existing root UUID. Reuse saved child/agent IDs on resumption. Root delegation is the only root SOP; Developer and Reviewer share one fixed feature skill; acceptance questions come from their issue. Use standalone repository-owned procedures and native Multica CLI actions. The product must not invoke system distribution, review or delivery SOP skills.

Developer and Reviewer have distinct native identities and separate contexts. Keep source edits, tests and approved integration with Developer. Reviewer only reads and returns approval or corrections. MAIN drafts the delegation, uses grilling to resolve one point per human question and edit, then dispatches directly and receives results. Preserve the original request, acceptance question, minimum review questions and review/rework loop.

Use `Workflow`, `State`, `Option` and declared prechecks from the current template. Each feature issue owns one SoP metadata record shared by both agents. Reject the wrong agent ID for the current phase. Let the platform own the issue folder and serialization; store no folder mapping or task ID. Publish findings, verdicts and delivery evidence as comments.

Keep tests under `tests/` small: installer resumption, delegation, branch/routing guards and one correction/integration smoke path. Use real workspace runs for native handoffs and HTML verification instead of duplicating the platform or generic runtime's test suite. Reuse settled evidence; run only checks affected by a change. Keep workspace evidence outside Git.

MAIN passes a short feature name; the installed direction prefix formats its branch. Developer starts directly on the issue's existing named branch. Neither Developer nor Reviewer names, creates or switches branches. They retain that one branch and current issue folder through review and corrections; never check out a separate review branch. Approval merges and tests or reports a manual-check note to MAIN, then finishes. Keep local configuration, generated packages, logs and credentials untracked. Preserve shared services and unrelated agents, skills, issues and data. Use ponytail and concise native replies.

## Implementation notes

Run local checks with `python3 -m unittest discover -s tests -v`. Build packages
with `packages.build('delegation', ..., binding=config)` or
`packages.build('feature', ...)`; each validates via `wrapper.py --validate`.
Use the [RSI creator](https://github.com/Winfred666/multica-RSI/blob/main/harness/skills/create-symbolic-sop/scripts/check.py)
for generic runtime protocol and renderer checks, not another copy here.

An existing installation's saved `root_issue_id` supports upgrades only. Preserve
its identity, history, labels and status. Explicitly subscribe `assigner_id` to
MAIN, defaulting to the installer issue's creator. Bind skills additively and publish the
selected directions in the project description. Missing answers return one
`needs_input` object and exit; never open an interactive questionnaire.

The feature procedure stores one current record under
`issue.metadata["sop.multica-featssship-develop-review"]`; completion removes only
that key. `--help` must not advance state. The first feature push requires an
unused remote name; amendments lease the previous submitted commit. Preserve
these checks without adding a global lock. See [docs/workflow.md](docs/workflow.md)
for routing, handoff output and debug graph behavior. The accepted runtime
protocol is [RSI 0fd1fbb4a](https://github.com/Winfred666/multica-RSI/commit/0fd1fbb4a).
