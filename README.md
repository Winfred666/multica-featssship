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
python3 /path/to/multica-featssship/install.py
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
