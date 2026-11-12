"""Two-stage installation: edit on the installer, publish a shared master configuration."""
import json

from common import WAIT_OUTER, attachment, cli, config_ref, link_config, merge_patch, read_config, write_config
from sop import FINISHED, Option, Parameter, State, Workflow

CACHE_VIEW = False

from install import defaults, execute

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
            'installed_* agent and skill IDs are reusable settings in the master attachment. '
            'Use a JSON merge patch: objects merge, arrays replace, null removes a field.')


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    if issue['workspace_id'] != context['workspace_id'] or issue.get('assignee_id') != context['agent_id']:
        raise context['error']('wrong_agent', 'Use the assigned installation issue and installer identity.')
    reference = config_ref(issue)
    if not reference:
        reference = {'issue_id': issue['id'], 'filename': 'featssship-config.json'}
        if not any(row['filename'] == reference['filename'] for row in issue.get('attachments', [])):
            write_config(reference, defaults(issue), context['args'].thread, 'Edit or confirm.')
        link_config(issue['id'], reference)
        issue['metadata']['featssship.config'] = reference
    context.update(config=read_config(reference), reference=reference, issue=issue)
    if context['args'].thread:
        context['state']['reply_parent'] = context['args'].thread


def view(context):
    return {'instruction': PROMPT + COMMENTS + '\n\nRead the latest configuration attachment: ' + json.dumps(context['reference'])}


def edit(args, context):
    """```dot
    digraph edit { node [shape=box]; patch [label="Merge JSON patch into current config"];
        save [label="Publish master JSON attachment revision"];
        publish [label="Attach JSON: edit or confirm; tell agent to exit"];
        patch -> save -> publish; }
    ```"""
    patch = json.loads(args.patch)
    if not isinstance(patch, dict):
        raise context['error']('invalid_input', '--patch must be a JSON object.')
    if any(key.startswith('installed_') or key.endswith('_id') for key in patch):
        raise context['error']('invalid_input', 'Use role.id to select an agent; installed_* IDs are maintained by installation.')
    config = merge_patch(context['config'], patch)
    row = write_config(context['reference'], config,
                       args.thread or context['state'].get('reply_parent') or context['state'].get('comment_id'), 'Edit or confirm.')
    context['state']['comment_id'] = row['id']
    context['state']['draft_attachment_id'] = attachment(context['reference'])['id']
    context['state'].pop('confirmed_comment_id', None)
    context['config'] = config
    args.patch = '{}'
    context['argv'] = ['edit', '--patch', '{}']
    return {'instruction': 'Configuration attached. Edit or confirm. ' + EDIT_DONE}


def confirmed(args, context):
    """```dot
    digraph confirmed { node [shape=box]; check [label="Require human confirmation of latest config"];
        install [label="Validate; resume this cycle or create another MAIN; install roles/skills"];
        inject [label="Link MAIN to the master attachment; remove legacy description block"];
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
                or state['draft_attachment_id'] != attachment(context['reference'])['id']):
            raise context['error']('invalid_input', 'A human must reply confirm after the latest config in its thread.')
        state['confirmed_comment_id'] = human['id']
        context['save_state']()
    execute(config, context['issue'], state, context['save_state'])
    cli('issue', 'status', context['issue_id'], 'done')


workflow = Workflow(
    State('grilling', PROMPT, initial=True, precheck=observed, view=view, options=(
        Option('edit', 'grilling', 'Update only the settings that need changing.', edit,
               params=(Parameter('--patch', 'JSON merge patch for the settings to change'),)),
        Option('confirmed', FINISHED, 'After the human replies confirm, run confirmed to install.', confirmed),
    )),
    params=(Parameter('--thread', 'Agent-only: native trigger comment (optional); confirmation is found automatically', required=False),),
)
