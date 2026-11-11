"""Two-stage installation: edit on the installer, confirm into MAIN metadata."""
import json
from pathlib import Path
import sys

from common import WAIT_OUTER, block, cli, comment, save_config, unpack
from sop import Option, Parameter, State, Workflow

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from install import defaults, execute, merge_patch

# TODO: Breaks the agent-as-middle-layer principle: the script cannot proactively
# take over human interaction or end the turn, so it must ask the agent to exit.
EDIT_DONE = 'Edit finished. ' + WAIT_OUTER
PROMPT = ('Adjust the config to match the requested workflow. Keep what already fits. '
          'Ask the human one question only if the context leaves something unclear. ' + WAIT_OUTER + ' ')
COMMENTS = ('Defaults: repository is the target Git URL, not the featssship source. '
            'Each directions entry owns name, scope (paths), Reviewer questions (string list), test_command and branch_prefix; '
            'replace the list to set all concurrent directions. Missing acceptance questions/test_command must be filled from context. '
            'Roles default to distinct new agents using the installer runtime/model; set role.id to reuse one. '
            'Blank model inherits the runtime default. A new cycle creates an independent MAIN; unfinished retries use its saved ID. CEO is subscribed. '
            'manual defaults to false; true requires superior approval after automated review and permits a remote feature branch. '
            'installed_* fields are script-owned audit checkpoints, retained only here. '
            'Use a JSON merge patch: objects merge, arrays replace, null removes a field.')


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    if issue['workspace_id'] != context['workspace_id'] or issue.get('assignee_id') != context['agent_id']:
        raise context['error']('wrong_agent', 'Use the assigned installation issue and installer identity.')
    config = defaults(issue)
    context.update(config=config, issue=issue)
    if context['args'].thread:
        context['state']['reply_parent'] = context['args'].thread


def view(context):
    return {'instruction': PROMPT + COMMENTS + '\n\nCurrent config:\n' + json.dumps(context['config'], indent=2)}


def edit(args, context):
    """```dot
    digraph edit { node [shape=box]; patch [label="Merge JSON patch into current config"];
        save [label="Save config on installation issue"];
        publish [label="Comment tidy JSON: edit or confirm; tell agent to exit"];
        patch -> save -> publish; }
    ```"""
    patch = json.loads(args.patch)
    if not isinstance(patch, dict):
        raise context['error']('invalid_input', '--patch must be a JSON object.')
    if any(key.startswith('installed_') or key.endswith('_id') for key in patch):
        raise context['error']('invalid_input', 'Use role.id to select an agent; installed_* fields are script-owned audit checkpoints.')
    config = merge_patch(context['config'], patch)
    save_config(context['issue_id'], config)
    row = comment(context['issue_id'], block('installation-config', config) + '\n\nEdit or confirm.',
                  args.thread or context['state'].get('reply_parent') or context['state'].get('comment_id'))
    context['state']['comment_id'] = row['id']
    context['state'].pop('confirmed_comment_id', None)
    context['config'] = config
    return {'instruction': 'Current config:\n' + json.dumps(config, indent=2) + '\n\n' + EDIT_DONE}


def confirmed(args, context):
    """```dot
    digraph confirmed { node [shape=box]; check [label="Require human confirmation of latest config"];
        install [label="Validate; resume this cycle or create another MAIN; install roles/skills"];
        inject [label="Copy process settings into MAIN metadata; remove legacy description block"];
        finish [label="Mark installer done"];
        check -> install -> inject -> finish; }
    ```"""
    state, config = context['state'], context['config']
    if not state.get('comment_id'):
        raise context['error']('invalid_input', 'Publish the config, then wait for the human to reply confirm.')
    if not state.get('confirmed_comment_id') or (args.thread and state['confirmed_comment_id'] != args.thread):
        rows = cli('issue', 'comment', 'list', context['issue_id'], '--thread', args.thread or state['comment_id'], '--tail', '30')
        draft = next((row for row in rows if row['id'] == state['comment_id']), None)
        human = next((row for row in reversed(rows)
                      if row['id'] == args.thread or (not args.thread and row.get('author_type') == 'member')), None)
        if (not draft or not human or human.get('author_type') != 'member'
                or human['content'].strip().casefold() != 'confirm'
                or rows.index(human) <= rows.index(draft)
                or unpack(draft['content'], 'installation-config') != config):
            raise context['error']('invalid_input', 'A human must reply confirm after the latest config in its thread.')
        state['confirmed_comment_id'] = human['id']
        context['save_state']()
    result = execute(config, context['issue'], state, context['save_state'])
    cli('issue', 'status', context['issue_id'], 'done')
    return {'instruction': 'Installation finished. Continue on MAIN ' + result['root_issue_id'] +
            ' using ' + result['command'] + '. Exit this round.'}


workflow = Workflow(
    State('grilling', PROMPT, initial=True, precheck=observed, view=view, options=(
        Option('edit', 'grilling', 'Update only the settings that need changing.', edit,
               params=(Parameter('--patch', 'JSON merge patch for the settings to change'),)),
        Option('confirmed', 'finished', 'After the human replies confirm, run confirmed to install.', confirmed),
    )),
    State('finished', 'Installation is complete; continue on MAIN.', final=True),
    params=(Parameter('--thread', 'Agent-only: native trigger comment (optional); confirmation is found automatically', required=False),),
)
