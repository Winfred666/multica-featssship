# multica-featssship

MAIN delegates; Developer implements and tests; Reviewer reviews and ships.

## Install

Requires Python 3.11+, Git and authenticated `multica`.

1. Create an installation issue in the target Multica project and assign an
   installer agent. Give it this README, the target repository and any known
   directions, runtime or model choices.
2. The installer reads its saved master JSON, creating defaults only when absent.
   Re-entry keeps your edited config. It asks one self-contained question at a
   time only when something is uncertain.
3. Download and review the attached JSON. Reply with changes or `confirm`.
4. After confirmation, installation creates an independent `MAIN DEV:` issue, sets up the
   agents and skills, and subscribes CEO. Installation can finish while MAIN continues independently.

### Installer agent

Reuse an available featssship checkout. In the assigned installation issue,
run from the **target repository checkout**:

```bash
python3 /path/to/multica-featssship/installation/install.py
```

Follow the returned editing and confirmation guidance. On a comment trigger,
pass `--thread <trigger UUID>`. Keep the source checkout until installation
finishes. Run it again after completion to install another MAIN using the saved
config, with a new edit/confirmation round. Retrying an unfinished round resumes
its MAIN without creating a duplicate. Existing MAIN issues are left unchanged.
Do not search for or ask the human to create a separate MAIN issue.

## Shipping overview

Describe a feature on MAIN. MAIN settles its config and delegates to Developer.
Reviewer approves or requests corrections in the same feature issue, then owns
approved integration, push and completion. Developer handles source corrections.

DEBUG mode publishes HTML state graphs during runs. See [workflow details](docs/workflow.md)
for development and protocol documentation.

## Configuration

The installer owns one logical `featssship-config.json`, including the repository,
parent branch, roles, directions, manual default and optional sandbox settings. MAIN stores only its
`featssship.config` reference, so another independent MAIN can reuse it without
installer ancestry. Entry creates defaults only when the document is absent.
Re-entry retains edits; confirmation starts another MAIN, while unfinished retries
resume the checkpointed MAIN.

Dispatch stores only request-specific overrides in a `featssship.delegation-<id>.json` from the settled request. Each read resolves universal settings and mention
agent IDs directly from the installer master, so they are never copied into delegations. MAIN and dev-rev share its `featssship.delegation`
reference. Dev-rev never creates a config. Metadata keeps these owner/filename
references and execution checkpoints only, not settings or cached JSON. The
feature keeps its base commit as an execution checkpoint for the push lease;
repository settings come from the master; the settled branch is request-specific.

Native mutable deliverables are not available in the current CLI. The temporary,
CEO-approved transport publishes immutable attachment revisions in the existing
comment thread. Grilling revisions say `Edit or confirm.`; other revision comments render empty.
Reads select the latest attachment with the referenced owner and filename, then
use authenticated `multica attachment download <id> --output-dir <directory>`.
An authorized edit uploads that same filename to its owner issue, under the
current thread; subsequent readers see it without relinking every MAIN. Old
attachments remain revision history, not alternate configuration sources. Keep
concurrent edits serialized; there is no native compare-and-swap. Configuration
and its attachments survive completion/cancellation. TODOs in the packaged `common.py` mark
the future native update/preview substitutions. Runtime `config.json` contains
only the standard symbolic-SoP DEBUG toggle, not shipping settings.
