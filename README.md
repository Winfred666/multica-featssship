# multica-featssship

Ship features with three agents: MAIN delegates, Developer implements and
integrates, and Reviewer independently approves or requests corrections.

## Install

Requires Python 3.11+, Git and authenticated `multica`.

1. Create an installation issue in the target Multica project and assign an
   installer agent. Give it this README and any known runtime/model choices.
2. Give the installer any known target repository, directions and role choices.
   It adjusts the config to match the requested workflow, keeping choices that
   already fit. It asks one human question only for genuine uncertainty.
3. The installer comments the filled config in the installation thread and asks
   **Edit or confirm.** Reply with changes or `confirm`.
4. Only after confirmation, installation creates its parked `MAIN DEV:` child,
   installs the skills, subscribes CEO and copies only process settings into MAIN metadata. It then
   marks the installation issue done. Continue on MAIN to ship features.

### For the installer agent

Reuse an available featssship checkout and facts already supplied. Run in the
assigned installation issue:

```bash
python3 /path/to/multica-featssship/install.py
```

There are only two states: `grilling` and `finished`. In grilling, inspect the
current JSON config and its default-value comments. Use
`edit --patch '<JSON merge patch>'` to change only what is needed for the requested
workflow. Return to editing as needed; keep choices that still fit. Objects merge, arrays replace,
and null removes a field. Each direction has a name, path scope, Reviewer
questions (a string list), test command and branch prefix. Role defaults
create distinct agents using the installer runtime/model; set `delegator.id`,
`developer.id` or `reviewer.id` to reuse agents. MAIN is found through the
installer's children, never through saved issue IDs.

On a comment trigger, pass `--thread <trigger UUID>`. After edit, the script
publishes tidy JSON and asks the human to edit or confirm. Exit silently as
instructed. The human only replies `confirm`, with no command or UUID. The agent
then runs `confirmed`; the script finds the reply in the config thread. It rejects
agent confirmations, stale confirmations and a newer human reply asking for changes.

Resume confirmed installation from the target repository checkout root. Keep
the featssship source checkout available until finished. Generated runtime code
lives in its ignored `.multica/featssship/installer/` directory. There is no local
answers or binding JSON: native issue metadata is the only source of truth for
installation settings. The generic runtime's `config.json` controls DEBUG only.

- **Installation issue**, `featssship.installation`: init settings (repository,
  role creation choices, direction scope/test command) and proven `installed_*`
  checkpoints for agents, skills, workspace and project. No issue IDs are saved.
- **MAIN**, `featssship.process`: direction names map only to `questions` and
  `branch_prefix`. MAIN resolves roles and init defaults through its installer
  parent. CEO is subscribed to MAIN.
- **Feature**, `featssship.process`: only its selected questions, full `branch`,
  `parent_branch` and any inherited sandbox process settings. The native request
  includes its scope and verification command, not copied installation bindings.

The project description receives repository/scope/test context, never review
questions or installed IDs. Upgrades replace only the installer's marked block
and remove the old full-config record from MAIN. Existing MAIN history, labels,
status and unrelated metadata/skills are preserved. After success, continue on
MAIN, not the installer.

## Ship a feature

On the MAIN child, describe the requested change, direction and acceptance
criteria. MAIN uses the installed delegation command from the target repository:

```text
propose --name tree-horizontal-more --request REQUEST --direction NAME
```

Review questions and branch prefix come from the selected direction in MAIN
metadata. Scope and test defaults are resolved through its installer parent. Override them with `--scope`, `--question` or `--test-command`
only for feature-specific criteria.

MAIN clarifies one point at a time with the human, uses `edit` to record each
answer, then calls `dispatch`. Give a short feature name; the selected direction
formats it as, for example, `feat/frontend/tree-horizontal-more`. Use
`--github-issue URL` to link a source issue when needed.

Developer implements and submits. Reviewer reads the submitted revision and
approves it or requests corrections in the same issue. Developer owns tests and
approved integration, then sends MAIN one verified result. A manual label keeps
integration pending human action. Human acceptance owns completion.

The agents' HTML state graphs show the current step during a run. See the
[shipping flow](docs/workflow.md) for the full graph.
