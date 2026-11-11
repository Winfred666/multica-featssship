# multica-featssship

Ship features with three agents: MAIN delegates, Developer implements and
integrates, and Reviewer independently approves or requests corrections.

## Install

Requires Python 3.11+, Git and authenticated `multica`.

1. Create an installation issue in the target Multica project and assign an
   installer agent. Give it this README, the target repository and any known
   directions or runtime/model choices.
2. The installer posts the config. Reply with changes or `confirm`.
3. After confirmation, the script installs the workflow, creates a `MAIN DEV:`
   child and subscribes CEO. Continue on MAIN to ship features.

### For the installer agent

Keep a featssship source checkout available until installation finishes. In the
assigned installation issue, run from the **target repository checkout**:

```bash
python3 /path/to/multica-featssship/install.py
```

Follow the returned commands. Adjust only settings that need changing; ask one
human question only when context cannot resolve a choice. On comment triggers,
add `--thread <trigger UUID>`.

After `edit`, exit silently as instructed. The human replies only `confirm`;
then run the returned `confirmed` command. Resume interrupted setup in the same
installation issue and target checkout.

## Ship a feature

Tell MAIN the requested change, direction and acceptance criteria. The MAIN
agent runs its installed delegation skill from the target repository and chooses:

```text
propose --name short-feature-name --request REQUEST --direction NAME
```

MAIN follows the returned choices to clarify only what is unclear, then dispatches.

Developer implements and tests; Reviewer approves or requests corrections.
Developer integrates approved work and reports to MAIN. A `manual` label keeps
integration pending human action. Human acceptance closes the issue.

See [workflow internals](docs/workflow.md) for state graphs and storage details.
