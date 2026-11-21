# multica-featssship

MAIN delegates; Developer implements and tests; Reviewer reviews and ships.

## Install

Requires Python 3.11+, Git and authenticated `multica` with `sop run` support.
Assign an installation issue in the target project with the target repository,
directions and known role/runtime choices. Review the saved JSON in the native
questionnaire: `confirm` installs; `request_edit` returns to drafting.
Confirmation creates/reuses the MAIN issue, sets up roles/local skills and subscribes CEO.
MAIN and Developer may reuse the same agent; Reviewer must be distinct from both.

### Installer agent

Build from a persistent featssship **source checkout** into the configured
**target Git checkout** (replace the example paths below). The destination is
`<target>/.agents/skills/multica-featssship-installation/`, including helpers and
child bundles. Run the SoP from the target root, not the source or `/tmp`.

```bash
cd /persistent/source/installation
python3 -c "from packages import build; build('installation', '/persistent/target/.agents/skills/multica-featssship-installation')"
cd /persistent/target
multica sop list
multica sop run multica-featssship-installation
```

`sop list` must show that installed path. Follow returned guidance; on comment
triggers pass `--thread <trigger UUID>`. Keep the target and bundle at these paths:
callbacks use saved `workdir` and rediscover `.agents/skills/`, not shell-only
`MULTICA_SOP_SKILL_ROOTS`. Every executing runtime needs access to these local files.

### Update

In the same installation issue, run `git -C /persistent/source pull --ff-only`,
rebuild the installer using the command above, then run from the target root:

```bash
multica sop run multica-featssship-installation update
```

`update` refreshes saved MAIN's delegation/context while keeping settings,
MAIN identity, progress and in-flight dev-rev copies. Do not repeat initial setup
or create another MAIN to repair a missing entrypoint.

## Shipping overview

Describe a batch of issues on MAIN. MAIN drafts one `{"issues":[...]}` config
(default: one item). Download and edit the whole JSON, then use
`refresh --config-file PATH` to publish it. The native questionnaire in the same
issue thread lets outer confirm dispatch directly or submit one batch-change
request to MAIN for drafting. Partial batches retry with `confirm` without
recreating children; do not edit a batch once a child exists.
Reviewer approves or requests corrections in the same feature issue, then owns
approved integration, push and completion. Developer handles source corrections.

DEBUG mode publishes HTML state graphs during runs. See [workflow details](docs/workflow.md)
for development and protocol documentation.

## Configuration

The installer owns `featssship-config.json`: repository, parent branch, roles,
directions, manual default and optional sandbox settings. Batch items contain
request-specific overrides; universal defaults still come from the installer.

Set `directions[].developer_id` to an existing agent UUID in the installer config:

```json
{"directions": [{
  "name": "frontend", "type": "dev", "developer_id": "DEVELOPER_UUID", "scope": "src/ui/",
  "questions": ["Does the UI match the requested behavior?"],
  "test_command": "git diff --check", "branch_prefix": "feat/frontend"
}]}
```

Precedence: delegation-item `developer_id` > selected direction `developer_id` >
installation-wide Developer. Submit with `publish --patch '<JSON>'`; outer still
confirms installation. The directions array replaces the whole list, so retain
existing directions, scopes and questions.

Draft publication writes config revisions; confirmation checkpoints role IDs in
metadata without publishing config. Use the latest draft and serialize edits.

### Split experiments

Set `directions[].type` to `exp` for experiments or `dev` for shipping (the default).
Both types can share one installation and batch. Direction names, scopes and review
questions still apply. For exp directions, `test_command: "evaluate.py"` names the canonical private
score script rather than a public shell test.

MAIN creates a Reviewer `exp` child. Reviewer prepares a Developer `exp` child
and sends its native development questionnaire there. Developer commits the
candidate and answers `candidate_ready` with the local pipeline and visual image
attachment; only Reviewer runs the split SoP. The fixed split project context
encourages ontology module dictionaries, connected pipelines and named variants.
Developer attaches an initial pipeline image and updates it as development proceeds.
Reviewer's `submit --review TEXT` action evaluates once, validates
`{"score": <finite number>}`, posts it plus review directly to MAIN and enters
terminal `finished`. Experiments never merge, integrate or push to main. MAIN's next
decision is outside this workflow; `manual` only controls normal shipping.

Real evaluation code/data and a dedicated Unix-account boundary must be supplied
before scoring. Different agent IDs or folders are not isolation. See the
[private evaluation contract](docs/workflow.md#private-evaluation-boundary).

感谢 [LINUX DO](https://linux.do/) 社区的支持。
