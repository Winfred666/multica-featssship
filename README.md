# multica-featssship

A standalone Developer–Reviewer shipping SOP. Start with the [shipping graph](docs/workflow.md).
MAIN supplies the feature branch. The child uses its current issue folder.

## One-time installation

Requires Python 3.11+, Git and authenticated `multica`; GitHub URLs are optional source links.
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
and the same `multica-featssship-develop-review` skill to Developer and Reviewer.

## Use

MAIN runs the installed delegation skill's `wrapper.py` from the target repository.
Draft with `propose --title TITLE --request REQUEST --direction NAME --scope SCOPE
--question QUESTION`. Resolve one unclear point per human question and `edit`,
then `dispatch`. An optional `--github-issue URL` mirrors an existing source issue;
it does not replace the delegated acceptance criteria.

The feature issue has one workflow: `develop → review → integrate → finished`; rework returns
to `develop`. Both agents use the same installed skill and issue folder. Only
the configured Developer can submit; only the configured Reviewer can judge.
Reviewer only reads and returns approval or corrections; no source writes, tests,
merge or push. Approval hands the approved revision back to Developer for tests,
integration and reporting. A manual label, merge conflict or failed check sends
MAIN a note and finishes. Wrong-role action calls reject on stderr without JSON or state
changes. Handoffs return only a plain stop message to the sender, not the next
role's JSON guidance. The receiving agent reads its own guidance on entry.

MAIN creates the remote feature branch before dispatch. The issue checkout must
already use that branch. Checkout provisioning belongs to installation/platform
setup; the child procedure never creates or switches folders or branches.
The child config contains only Developer ID, Reviewer ID, branch and test command.
Request, scope and acceptance stay in the issue description; parent identity comes
from the native parent issue.

The standalone runtime follows the accepted issue-state protocol from
[RSI 0fd1fbb4a](https://github.com/Winfred666/multica-RSI/commit/0fd1fbb4a).
One current record under `issue.metadata["sop.multica-featssship-develop-review"]`
contains guidance and submitted revision; completion removes only that key.
`--help` reads without advancing. Controller data is internal. No task ID, local
state file, folder mapping or comment-history replay is needed. Existing live
installations are left on their installed version until explicitly upgraded.

## Development

Run `python3 -m unittest discover -s tests -v`. Fixtures use two native agent
identities, simulated Multica calls and a real Git remote to check correction,
merge, role rejection and manual handoff. MAIN installation/delegation remains
separate from the small feature procedure in [roles/feature.py](roles/feature.py).
Build with `packages.build('delegation', ..., binding=config)` or
`packages.build('feature', ...)`; each validates with `wrapper.py --validate`.
The canonical nine protocol checks live in the
[RSI creator](https://github.com/Winfred666/multica-RSI/blob/main/harness/skills/create-symbolic-sop/scripts/check.py).
