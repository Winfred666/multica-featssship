# Developing multica-featssship

Read README.md and docs/workflow.md. Build the smallest complete Developer–Reviewer prototype using the bundled Symbolic-SoP runtime. Keep this repository atomic; do not add submodules.

Keep one commit per feature. Amend corrections and finish verification before pushing.

Declare global routing in Workflow and local action logic in short DOT docstrings. Reuse the RSI creator for protocol and renderer maintenance. Keep prompts limited to inputs, entry, judgment and exception handling. README covers installation and usage.

The first assigned prototype issue is explicitly authorized to develop and commit directly on `main`. It carries `dev` and `manual`; human review owns acceptance. Verify its repository and branch before editing. Report the prototype in its native issue and wait for human acceptance. Do not create a PR unless requested.

Installation is a one-time README-guided script. Root delegation is the only root SOP; Developer and Reviewer share one fixed feature skill; acceptance questions come from their issue. Use standalone repository-owned procedures and native Multica CLI actions. The product must not invoke system distribution, review or delivery SOP skills.

Developer and Reviewer have distinct native identities and separate contexts. Keep source edits with Developer, acceptance with Reviewer, and approved integration with Reviewer. MAIN drafts the delegation, uses grilling to resolve one point per human question and edit, then dispatches directly and receives results. Preserve the original request, acceptance question, minimum review questions and review/rework loop.

Use `Workflow`, `State`, `Option` and declared prechecks from the current template. Each feature issue owns one SoP metadata record shared by both agents. Reject the wrong agent ID for the current phase. Let the platform own the issue folder and serialization; store no folder mapping or task ID. Publish findings, verdicts and delivery evidence as comments.

Keep tests under `tests/`. Run focused checks for changed behavior, validate generated wrappers with `--validate`, and use one disposable workflow trial for the actual handoff and merge path. Reuse settled evidence. A later sub-workspace trial against multica-RSI must remain separate from production workflows.

Use the supplied feature branch in the current issue folder. Approval merges and tests or reports a manual-check note to MAIN, then finishes. Keep local configuration, generated packages, logs and credentials untracked. Preserve shared services and unrelated agents, skills, issues and data. Use ponytail and concise native replies.
