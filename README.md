# multica-featssship

A standalone Developer–Reviewer shipping SOP. Start with the [shipping graph](docs/workflow.md).
Each controller declares its state graph and documents local callback logic.

## One-time installation

Requires Python 3.11+, Git and authenticated `multica`; linked GitHub requests also
require authenticated `gh` access to read, comment on and close the source issue.
HTML preview compilation reuses Graphviz's `dot` on PATH or automatically installs
`graphviz` with the host package manager. Installation failures report
`dependency_install_failed`; resolve the reported error before retrying.
Run the installer from the target repository checkout:

```bash
git clone https://github.com/Winfred666/multica-featssship.git
cd /path/to/target-repository
python3 /path/to/multica-featssship/install.py --config /path/outside-repository/featssship-answers.json
```

The installer asks for missing values and saves successful IDs in the answers
file. Rerun with that file to reuse agents, skills and the existing root. MAIN,
Developer and Reviewer must be distinct agents in the selected workspace.

For unattended installation:

```json
{
  "workspace_id": "<workspace UUID>",
  "project_id": "<project UUID>",
  "root_issue_id": "<existing agent-assigned MAIN root UUID>",
  "repository": "https://github.com/owner/target",
  "developer_id": "<existing Developer UUID>",
  "reviewer_id": "<different existing Reviewer UUID>",
  "directions": [{
    "name": "editor",
    "scope": "src/editor and its focused tests",
    "question": "Can a user save and reopen the edited document?",
    "test_command": "python3 -m unittest discover -s tests/editor"
  }]
}
```

To create a role, replace its `_id` with an object such as
`"developer": {"name": "Developer", "runtime_id": "<runtime UUID>", "model": "<chosen model>"}`.
The existing root's assignee is MAIN. Installation preserves its ID, history,
labels and status, prefixes its title with `MAIN DEV:`, and publishes selected
scopes/questions/tests in the project description. It binds delegation to MAIN
and the same `multica-featssship-feature` skill to Developer and Reviewer.

## Use

MAIN runs the installed delegation skill's `entry.py` from the target repository.
Draft with `propose --title TITLE --request REQUEST --direction NAME --scope SCOPE
--question QUESTION`. Resolve one unclear point per human question and `edit`,
then `dispatch`. An optional `--github-issue URL` mirrors an existing source issue;
it does not replace the delegated acceptance criteria.

The feature issue has one shipping workflow: `implement → review → integrate →
finished`, with rework returning to `implement`. Developer and Reviewer call the
same skill in the same issue checkout. Phase prechecks reject the wrong native
agent ID. Questions and evidence stay on the issue; no per-review skill is built.
MAIN only dispatches and receives. Human acceptance owns done.

This uses the accepted issue-state protocol from
[RSI 0fd1fbb4a](https://github.com/Winfred666/multica-RSI/commit/0fd1fbb4a).
Shared issue folders still await the separate R-269 deployment, which serializes
agents within an issue and isolates different issues. The runtime stores one
current record under `issue.metadata["sop.multica-featssship-feature"]`; completion
removes only that key. No task ID, local status file, review checkout or folder
mapping is needed. Static installation answers and package settings remain local.
Existing task-local sessions are preserved, not automatically migrated: finish
them with their installed version before binding the shared package.

Use `--thread <trigger UUID>` on comment-triggered calls. `--help` reads current
guidance without running an action. Output contains status, instructions, callback
commands, errors and needed recovery facts; binding data and findings are not echoed every time.
An approval applies to one exact submitted revision. Integration tests the merged
revision in a disposable checkout, preserves the issue checkout on failure, and
reports one verified result to MAIN. Linked GitHub requests close only after a
successful push, with Developer's resolution and integrated commit.

## Development

Run `python3 -m unittest discover -s tests -v`. The fixture uses real Git with a
local CLI stand-in and exercises shared state, both identities, correction,
independent approval, manual holds, integration and delivery retries across two
installed package directories sharing the same issue state.
Run `python3 tests/check_symbolic_sop.py <package-directory>` for the canonical
nine protocol checks; its only packaging change is the bundled template path.
Build standalone packages with `packages.build('delegation', ..., binding=config)`
and `packages.build('feature', ...)`; both validate with `wrapper.py --validate`.
See [the short authoring guide](docs/symbolic-sop-authoring.md). Runtime and preview
details are in [the creator debugging reference](docs/DEBUG.md).
