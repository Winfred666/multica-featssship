# multica-featssship

Ship a requested feature or fix through separate Developer and Reviewer agents in one Multica issue. MAIN delegates the request and receives the verified result. The agent executing the workflow performs integration.

This is the prototype specification and authoring scaffold. Executable installation and delegation are the first implementation milestone.

The repository follows AIDE's portable configuration and local-skill packaging pattern. It is atomic: all implementation and required Symbolic-SoP runtime files live here, without submodules. The product uses repository-owned procedures instead of system review or delivery SOP skills.

## One-time installation guide

Installation is an ordinary script guided by this README, separate from the delegation SOP. The prototype must implement this sequence:

1. Select the target workspace, project, existing root issue, target repository and `main` branch. Use the existing Multica runtime and its native credentials.
2. Select existing Developer and Reviewer agents or create missing agents using explicitly chosen runtime/model settings. Bind distinct identities and separate contexts. Reuse existing agents without changing unrelated configuration; configure this workflow to use its local procedures.
3. Ask for each concurrent direction's name, scope, acceptance question and test command. Save those answers in ignored local configuration and render the direction/scope/test split into the target project's description. Ask only for unanswered inputs.
4. Polish the existing root issue's description in place and set its title to start with the literal `MAIN DEV:`. Its responsibilities are to delegate feature/fix requests and receive results. Preserve the root issue ID and native history.
5. Install the repository-owned delegation entrypoint and fixed Developer skill into the selected target. Record the selected native IDs for reuse on repeat installation. Finish installation with the exact delegation command and its inputs.

The prototype must document its actual installation command here. Generated state, credentials and local answers stay outside versioned software. Repeating installation reuses its owned records; it does not duplicate agents or roots.

## Delegation SOP

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

See [workflow design](docs/workflow.md) and the [current Symbolic-SoP authoring guidance](docs/symbolic-sop-authoring.md). The unmodified runtime template is included in [templates/symbolic-sop](templates/symbolic-sop/).

## Prototype development

The first DEV issue works directly on `main` and carries `manual`. Use Python 3.11+ and a small dependency footprint. Implement the one-time installation script, root delegation SOP, fixed Developer skill and generated Reviewer package as one complete prototype.

Use focused repository tests under `tests/`, validate every generated standalone wrapper with `--validate`, and exercise one disposable feature through a correction and successful integration. The later live target is a dedicated sub-workspace using multica-RSI. Installation into that target is a later stage; keep existing Research and RSI workflows untouched during prototype construction.

References: [multica-AIDE](https://github.com/Winfred666/multica-AIDE), [AIDE outer harness](https://github.com/WinfredClaw/multica-AIDE), [Anthropic independent review](https://code.claude.com/docs/en/best-practices#give-claude-a-check-to-run), [OpenAI reviewer example](https://learn.chatgpt.com/docs/agent-configuration/subagents#example-1-pr-review).
