# multica-featssship

A standalone Developer–Reviewer shipping SOP. Start with the [shipping graph](docs/workflow.md)
and [MAIN's delegation graph](DEBUG.md); callback details live in each role's graphs.

## One-time installation

Requires Python 3.11+, Git and authenticated `multica`; linked GitHub requests also
require authenticated `gh` access to read, comment on and close the source issue.
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
labels and status, prefixes its title with `MAIN DEV:`, publishes direction
scopes/questions/tests in the project description and adds the owned skills to
agents.

| Local resource | Location |
| --- | --- |
| Installed skills | `.agents/skills/multica-featssship*` |
| Generated packages and integration checkouts | `.multica/featssship` |
| Answers and credentials | Outside the repository |

The installer adds local Git exclusions for generated resources. Retain its
answers file and reserved package names; reconcile native state before retrying
an uncertain external write.

## Delegation

Start MAIN's installed entry command and follow the `drafting` state's guidance.
Its proposal input is:

```text
propose --title "Editor: save documents" --request "Save and reopen edits." --direction editor --scope "src/editor" --question "Can edits be saved and reopened?"
```

To reopen a draft in a new native task, pass `--spec <draft UUID>` and choose
`propose`. On a comment trigger, also pass `--thread <reply UUID>`.

| Optional proposal input | Meaning |
| --- | --- |
| `--test-command TEXT` | Verification command; defaults to the configured direction |
| `--github-issue URL` | Existing source link; a linked title also works |
| `--thread UUID` | Native trigger comment to reply under |

See the [specification and delegation graph](DEBUG.md).

## Acceptance and delivery reference

A human releases a `manual` hold by replying in the feature thread with the
approved full commit SHA:

````text
<!-- featssship:accept -->
```json
{"commit": "<approved full commit SHA>"}
```
````

Developer supplies `submit --summary "<outcome; approach; necessary links or artifacts>"`;
`--answer` is optional. The script reports added/deleted text lines, touched-file
and binary counts, and the three largest file diffs (ties by path; binary lines
are `null`). It compares the submitted commit to its merge base with fetched main.

## Development checks

```bash
python3 -m unittest discover -s tests -v
python3 wrapper.py --validate
```

Tests also validate generated role wrappers. Set `FEATSSSHIP_EVIDENCE` to an
external JSON path to retain disposable-fixture evidence. See
[AGENTS.md](AGENTS.md) for development constraints and
[Symbolic-SoP authoring](docs/symbolic-sop-authoring.md) for the bundled runtime.
