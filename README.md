# multica-featssship

Ship a requested feature or fix through separate Developer and Reviewer agents in one Multica issue. MAIN delegates the request and receives the verified result. The agent executing the workflow performs integration.

This prototype includes a README-guided installer, one root delegation SOP, a fixed Developer skill and a question-specific compiled Reviewer. Python 3.11+, Git and an authenticated `multica` CLI are required.

The repository follows AIDE's portable configuration and local-skill packaging pattern. It is atomic: all implementation and required Symbolic-SoP runtime files live here, without submodules. The product uses repository-owned procedures instead of system review or delivery SOP skills.

## One-time installation guide

Installation runs once in the **target repository checkout**. Clone this package
beside that checkout, then run:

```bash
git clone https://github.com/Winfred666/multica-featssship.git
cd /path/to/target-repository
python3 /path/to/multica-featssship/install.py --config /path/outside-repository/featssship-answers.json
```

Use native Multica credentials for the selected workspace. The installer asks only
for missing answers. It collects workspace/project UUIDs, the existing root issue
UUID, target repository URL, and each direction's name, scope, acceptance question
and test command. For each role, select an existing agent UUID or explicitly choose
a name, runtime UUID and model to create one. MAIN, Developer and Reviewer are
separate identities. Existing agents keep unrelated configuration and skills.

For unattended installation, supply the same answers as JSON:

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

To create a missing role, replace its `_id` with an object such as
`"developer": {"name": "Developer", "runtime_id": "<runtime UUID>", "model": "<chosen model>"}`.
The existing root's assignee is MAIN. Successful agent and skill IDs are saved in
the answers file after each step. Rerunning with that file reuses those records
and replaces only the managed description sections. After an uncertain CLI write,
inspect native state and reconcile the saved IDs before retrying.

The installer preserves root ID, history, labels and status; its title begins with
exactly `MAIN DEV:`. The project description shows all configured concurrent
directions, their scopes, questions and checks. It imports self-contained local
archives and additively binds the root and Developer packages. Package names are
reserved for this installation; retain the answers file to update them in place.

Local copies live in `.agents/skills/multica-featssship*`; generated packages and
integration checkouts live in `.multica/featssship`. Git's local exclude file keeps
these out of source. Answers and credentials belong outside the repository.
The final installer output contains the root entry command and dispatch inputs.

## Delegation SOP

From MAIN's native task, start the installed root wrapper printed by installation,
then follow its `dispatch` callback:

```text
dispatch --title "Editor: save documents" --request "Save and reopen edits." --direction editor
```

Use `--question` to override that direction's acceptance question. For a
comment-triggered run, add `--thread <native trigger comment UUID>`. Each dispatch
creates one feature issue and a receipt thread under MAIN. MAIN ends its turn.
The feature is parked until its binding and Reviewer package are ready, then
starts Developer. Child runs use the bound skill's `entry.py` from their target
repository root; it materializes a local standalone wrapper and preserves task
state. The fixed Developer procedure creates `featssship/<issue UUID>` from main.

The repository root exposes one delegation SOP. It receives the feature/fix request, direction and acceptance question, creates one feature issue/branch, and compiles the Reviewer procedure from that question plus the default review questions.

The fixed Developer skill and compiled Reviewer skills are supporting packages, not additional root delegation SOPs. Install them into the target repository's local skill area and give child runs an entry command anchored to that repository root. Normal repository skills may coexist with these packages.

- Developer implements, runs the configured focused checks and mentions the bound Reviewer with the submitted commit and evidence.
- Reviewer independently inspects that commit against the original request and acceptance question, leaves source unchanged, and approves or returns concrete corrections in the same issue.
- The agent executing the workflow merges the approved commit through serialized integration, runs the configured checks and pushes after success. It sends MAIN one result with the verdict, integrated revision and concise evidence. Existing human holds remain effective.

Every feature/fix issue includes these default review questions, supplemented by its requested acceptance question:

1. Does the delivered behavior satisfy the request and acceptance evidence?
2. Are the additions necessary for the requested outcome?
3. Does the solution preserve the requested demand without shifting scope?

Each agent invokes its procedure within its own native `MULTICA_TASK_ID` and issue. Cross-agent transitions use native comments/mentions; an invocation cannot impersonate another agent or borrow its task ID. Review and delivery records live in comments, not issue metadata.

A `manual` label holds integration until a human replies in the feature thread
with the following native acceptance record for the approved full commit SHA:

````text
<!-- featssship:accept -->
```json
{"commit": "<approved full commit SHA>"}
```
````

A failed merge or integration check returns to Developer. Correct the feature
against current main, commit and submit again; Reviewer must approve that new
submission. Successful integration moves the feature to `in_review`; a human owns
`done`. The result notice to MAIN contains the Reviewer answer, approved commit,
integrated revision, check output and native review reference.

See [workflow design](docs/workflow.md) and the [current Symbolic-SoP authoring guidance](docs/symbolic-sop-authoring.md). The unmodified runtime template is included in [templates/symbolic-sop](templates/symbolic-sop/).

## Prototype development

Run the focused fixture and root validation:

```bash
python3 -m unittest discover -s tests -v
python3 wrapper.py --validate
```

The tests validate installed root, Developer and compiled Reviewer wrappers. The
fixture uses a simulated native CLI with separate identities/task IDs and real
Git commits, worktrees, merges and pushes to a disposable bare remote. To save its
measured evidence outside source, set `FEATSSSHIP_EVIDENCE=/absolute/external/file.json`.
It demonstrates installation reuse, rejection/correction/approval, integration and
one MAIN receipt; it also exercises manual holds and changed-branch rejection.
This proves script behavior, not live agent judgment or Multica server routing.

The first DEV issue works directly on `main` and carries `manual`. Use Python 3.11+ and a small dependency footprint. The package has no third-party Python dependencies.

Use focused repository tests under `tests/`, validate every generated standalone wrapper with `--validate`, and exercise one disposable feature through a correction and successful integration. The later live target is a dedicated sub-workspace using multica-RSI. Installation into that target is a later stage; keep existing Research and RSI workflows untouched during prototype construction.

References: [multica-AIDE](https://github.com/Winfred666/multica-AIDE), [AIDE outer harness](https://github.com/WinfredClaw/multica-AIDE), [Anthropic independent review](https://code.claude.com/docs/en/best-practices#give-claude-a-check-to-run), [OpenAI reviewer example](https://learn.chatgpt.com/docs/agent-configuration/subagents#example-1-pr-review).
