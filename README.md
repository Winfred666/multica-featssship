# multica-featssship

MAIN delegates; Developer implements and tests; Reviewer reviews and ships.

## Install

Requires Python 3.11+, Git and authenticated `multica` with `sop run` support.

1. Create an installation issue in the target Multica project and assign an
   installer agent. Give it this README, the target repository and any known
   directions, runtime or model choices.
2. The installer reads its saved master JSON, creating defaults only when absent.
   It asks one self-contained question only when something is uncertain.
3. Download and review the attached JSON. In the questionnaire, choose `confirm`
   to install or `request_edit` with a change request for the installer.
4. After confirmation, installation creates an independent `MAIN DEV:` issue, sets up the
   agents, deploys repository-local skills to `.agents/skills/`, and subscribes CEO.

### Installer agent

Reuse an available featssship checkout. In the assigned installation issue,
run from the **target repository checkout**:

```bash
MULTICA_SOP_SKILL_ROOTS=/path/to/multica-featssship multica sop run multica-featssship-installation
```

Follow the returned editing and confirmation guidance. On a comment trigger,
pass `--thread <trigger UUID>`. Keep the source checkout during installation.
Installation retains its existing MAIN checkpoint after completion and on retries.
Do not search for or ask the human to create a separate MAIN issue.

### Update

In the same installation issue, fast-forward the featssship source checkout,
then run from the **target repository checkout**:

```bash
git -C /path/to/multica-featssship pull --ff-only
MULTICA_SOP_SKILL_ROOTS=/path/to/multica-featssship multica sop run multica-featssship-installation update
```

The retained `finished` state offers only `update` and returns there afterward.
Update retrieves the saved MAIN and refreshes its local delegation bundle and
installation-managed entry/context references. It preserves settings, MAIN identity
and delegation progress; it does not rebind platform skills or change existing
dev-rev issues or their local packages. A standalone installer must be rebuilt
from the latest source before running `multica sop run multica-featssship-installation update`.

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
  "name": "frontend", "developer_id": "DEVELOPER_UUID", "scope": "src/ui/",
  "questions": ["Does the UI match the requested behavior?"],
  "test_command": "git diff --check", "branch_prefix": "feat/frontend"
}]}
```

Precedence: delegation-item `developer_id` > selected direction `developer_id` >
installation-wide Developer. Submit with `publish --patch '<JSON>'`; outer still
confirms installation. The directions array replaces the whole list, so retain
existing directions, scopes and questions.

Edits publish attachment revisions with the same filename. Use the latest
revision and serialize edits. See [workflow details](docs/workflow.md) for
configuration transport and implementation notes.
