# multica-featssship

MAIN delegates; Developer implements and tests; Reviewer reviews and ships.

## Install

Requires Python 3.11+, Git and authenticated `multica`.

1. Create an installation issue in the target Multica project and assign an
   installer agent. Give it this README, the target repository and any known
   directions, runtime or model choices.
2. The installer reads its saved master JSON, creating defaults only when absent.
   It asks one self-contained question only when something is uncertain.
3. Download and review the attached JSON. Reply with changes or `confirm`.
4. After confirmation, installation creates an independent `MAIN DEV:` issue, sets up the
   agents, deploys repository-local skills to `.agents/skills/`, and subscribes CEO.

### Installer agent

Reuse an available featssship checkout. In the assigned installation issue,
run from the **target repository checkout**:

```bash
python3 /path/to/multica-featssship/installation/install.py
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
python3 /path/to/multica-featssship/installation/install.py update
```

The retained `finished` state offers only `update` and returns there afterward.
Update retrieves the saved MAIN and refreshes its local delegation bundle and
installation-managed entry/context references. It preserves settings, MAIN identity
and delegation progress; it does not rebind platform skills or change existing
dev-rev issues or their local packages. A standalone installer must be rebuilt
from the latest source before running its `wrapper.py update`.

## Shipping overview

Describe a batch of issues on MAIN. MAIN drafts one `{"issues":[...]}` config
(default: one item). Download and edit the whole JSON, then use
`refresh --config-file PATH` to replace it. Confirm or accept the latest draft in
your own words. MAIN runs `dispatch` directly from grilling; it checks that human
approval before creating children or branches. Partial batches stay in grilling
and resume without recreating children.
Reviewer approves or requests corrections in the same feature issue, then owns
approved integration, push and completion. Developer handles source corrections.

DEBUG mode publishes HTML state graphs during runs. See [workflow details](docs/workflow.md)
for development and protocol documentation.

## Configuration

The installer owns `featssship-config.json`: repository, parent branch, roles,
directions, manual default and optional sandbox settings. Batch items contain
request-specific overrides; universal defaults still come from the installer.

Edits publish attachment revisions with the same filename. Use the latest
revision and serialize edits. See [workflow details](docs/workflow.md) for
configuration transport and implementation notes.
