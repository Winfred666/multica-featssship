# multica-featssship

MAIN delegates, Developer implements and integrates, and Reviewer independently
approves or requests corrections.

## Install

Requires Python 3.11+, Git and authenticated `multica`.

1. Create an installation issue in the target Multica project and assign an
   installer agent. Give it this README, the target repository and any known
   directions, runtime or model choices.
2. The installer prepares the JSON config, reusing supplied facts. It asks one
   self-contained question at a time only when something is uncertain.
3. Review the posted config. Reply with changes or `confirm`.
4. After confirmation, installation creates its `MAIN DEV:` child, sets up the
   agents and skills, and subscribes CEO. Continue on MAIN when installation ends.

### Installer agent

Reuse an available featssship checkout. In the assigned installation issue,
run from the **target repository checkout**:

```bash
python3 /path/to/multica-featssship/installation/wrapper.py
```

Follow the returned editing and confirmation guidance. On a comment trigger,
pass `--thread <trigger UUID>`. Keep the source checkout until installation
finishes. Do not search for or ask the human to create a separate MAIN issue.

## Shipping overview

Describe a feature on MAIN. MAIN settles its config and delegates to Developer.
Reviewer approves or requests corrections in the same feature issue. Developer
owns verification and approved integration, then reports the result to MAIN.
Human acceptance owns completion.

DEBUG mode publishes HTML state graphs during runs. See [workflow details](docs/workflow.md)
for development and protocol documentation.

## Source bundles

```text
installation/        README-guided installer and package builder
delegation/           MAIN request configuration and dispatch
delegation/dev-rev/   Shared Developer–Reviewer procedure
```

Each folder is a standard symbolic-SoP with its own `SKILL.md`, `controller.py`,
`wrapper.py`, `sop.py`, `monitor.py` and runtime `config.json`. Run its `wrapper.py`
from the target repository root. `installation/install.py` is an equivalent
installer entry point. Skill names and issue metadata keys are unchanged.

The bundles carry identical copies of the shared runtime and `common.py` so
that delegation and dev-rev run without the installer or source checkout. No
separate `templates/symbolic-sop/` is retained; the procedure folders contain the
runtime they use. Use the RSI creator for runtime maintenance.

`config.json` contains runtime settings only (`DEBUG`). Installation settings,
MAIN request config and child process config still live in issue metadata.
Delegation and dev-rev request configurations are authored when needed and copied
to sub-issues by the existing workflow, not stored as repository JSON drafts.

From `installation/`, call `packages.build('installation', destination)`,
`packages.build('delegation', destination)` or `packages.build('feature', destination)`.
The `feature` build selects `delegation/dev-rev/`; it keeps the installed name
`multica-featssship-develop-review`. Each build validates its wrapper and preserves
an existing runtime config. A standalone installer package includes delegation
and dev-rev as child bundles so confirmation can build and install both skills
without reaching back into this checkout.

Run local checks from this repository root:

```bash
python3 -m unittest discover -s tests -v
git diff --check
```
