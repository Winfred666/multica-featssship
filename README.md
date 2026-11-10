# multica-featssship

Ship features with three agents: MAIN delegates, Developer implements and
integrates, and Reviewer independently approves or requests corrections.

## Install

Requires Python 3.11+, Git and authenticated `multica`.

1. Create an installation issue in the target Multica project and assign an
   installer agent. Give it this README and any known runtime/model choices.
2. Tell the installer which repository needs featssship. If it is not known,
   the installer asks: **Which target repository needs featssship?** Give the
   Git URL of the code you want to ship, not necessarily this repository.
3. Answer one question at a time about each direction's name, code scope,
   acceptance question and test command. Choose distinct Developer and Reviewer
   agents, or the runtimes and models for creating them. New Developer and Reviewer
   agents default to GPT-6-Luna with high reasoning; choose a compatible Pi runtime.
   Explicit model and reasoning choices override these defaults.
4. Installation creates its own `MAIN DEV:` child issue. MAIN defaults to the
   installer's runtime and model. Continue on that child when setup is complete;
   you do not need to find or create a separate MAIN issue.

### For the installer agent

Reuse an available featssship checkout and facts already supplied. Run:

```bash
python3 /path/to/multica-featssship/install.py \
  --config /path/outside-repository/featssship-answers.json
```

When the script returns `needs_input`, ask only its `question` in the triggering
thread and end the turn. Save the reply under the returned `field` in the answers
file, then rerun the same command. A field such as `directions.0.scope` means
`scope` in the first direction. Keep the same answers file throughout.

Once the target repository is known, resume from its checkout root. Keep answers
and generated files out of Git. Reuse supplied agent IDs; resolve runtime choices
from the catalog instead of asking the human for UUIDs. On success, use the
returned command on the returned MAIN child, not the installation issue.

## Ship a feature

On the MAIN child, describe the requested change, direction and acceptance
criteria. MAIN uses the installed delegation command from the target repository:

```text
propose --name tree-horizontal-more --request REQUEST --direction NAME --scope SCOPE --question QUESTION
```

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
