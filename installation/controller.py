"""Draft configuration, collect native outer confirmation and retain installation."""
import json

from featssship import cli, config_ref, link_config, merge_patch, read_config
from thread import reply_parent, wake_callback, write_config
from sop import Option, Parameter, State, Workflow

CACHE_VIEW = False

from install import defaults, execute, update

PROMPT = ('Adjust the config to match the requested workflow. Keep what already fits. '
          'Ask the human one question only if the context leaves something unclear. ')
COMMENTS = ('Defaults: repository is the target Git URL, not the featssship source. '
            'Each directions entry owns type (dev or exp, default dev), name, scope (paths), Reviewer questions (string list), test_command and branch_prefix; '
            'optional developer_id selects an existing developer agent UUID for that direction. '
            'Developer precedence: delegation item developer_id, then direction developer_id, then the installed global Developer. '
            'replace the list to set all concurrent directions. Missing acceptance questions/test_command must be filled from context. '
            'Roles default to new agents using the installer runtime/model; set role.id to reuse one. MAIN and Developer may share an agent; Reviewer must be distinct from both. '
            'Blank model inherits the runtime default. Installation creates one MAIN issue; retries and updates use its saved ID. CEO is subscribed. '
            'manual defaults to false; true requires superior approval after automated review and permits a remote feature branch. '
            'Experiment directions retain scope/questions; set test_command to evaluate.py, the private canonical score script, not a public shell command. '
            'Never put hidden data, evaluator code or credentials in this shared attachment. '
            'Use a JSON merge patch: objects merge, arrays replace, null removes a field.')


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    if issue['workspace_id'] != context['workspace_id'] or issue.get('assignee_id') != context['agent_id']:
        raise context['error']('wrong_agent', 'Use the assigned installation issue and installer identity.')
    reference = config_ref(issue)
    if not reference:
        reference = {'issue_id': issue['id'], 'filename': 'featssship-config.json'}
        if not any(row['filename'] == reference['filename'] for row in issue.get('attachments', [])):
            write_config(context, reference, defaults(issue))
        link_config(issue['id'], reference)
        issue['metadata']['featssship.config'] = reference
    context.update(config=read_config(reference), reference=reference, issue=issue)


def view(context):
    return {'instruction': PROMPT + COMMENTS + '\n\nRead the latest configuration attachment: ' + json.dumps(context['reference']) +
            '\nRequested changes: ' + context['state'].get('change_request', 'Prepare the initial configuration.')}


def outer_owner(context):
    return {'issue_id': context['issue_id'], 'thread': reply_parent(context),
            'id': None, 'content': '/note'}


def publish(args, context):
    patch = json.loads(args.patch)
    if not isinstance(patch, dict):
        raise context['error']('invalid_input', '--patch must be a JSON object.')
    if any(key.startswith('installed_') or key.endswith('_id') for key in patch):
        raise context['error']('invalid_input', 'Use role.id to select an agent; installed_* IDs are maintained by installation.')
    config = merge_patch(context['config'], patch)
    write_config(context, context['reference'], config,
                 context['state'].get('change_request', 'Initial configuration.'))
    return {'this_round_reply_guidance': 'End this turn silently.'}


def request_edit(args, context):
    context['state']['change_request'] = args.change_request
    wake_callback(context, context['issue']['assignee_id'], 'Configuration changes requested: ' + args.change_request)


def confirm(args, context):
    execute(context['config'], context['issue'], context['state'], context['save_state'])
    cli('issue', 'status', context['issue_id'], 'done')


def refresh(args, context):
    update(context['config'], context['issue'], context['state'])


workflow = Workflow(
    State('edit', PROMPT, initial=True, precheck=observed, view=view,
          preview='Draft {reference}; requested changes: {change_request}.'),
    Option('publish', 'Publish the configuration for outer confirmation; use {} if no edits are needed.', publish,
           params=(Parameter('--patch', 'JSON merge patch for the settings to change'),)),
    State('outer_decide', 'Confirm configuration.',
          precheck=observed, owner=outer_owner),
    Option('confirm', 'confirm', confirm),
    Option('request_edit', 'edit', request_edit,
           params=(Parameter('--change-request', 'Changes to make to the configuration'),)),
    State('finished', 'Installation retained for the existing MAIN. On an update request, use the latest featssship '
          'source checkout or rebuilt installer and run update from the target repository. Otherwise, end this turn.',
          precheck=observed),
    Option('update', 'Refresh the saved MAIN’s local delegation and installation-managed context; keep in-flight dev-rev copies.', refresh),
    edges=(
        ('edit', 'publish'), ('publish', 'outer_decide'),
        ('outer_decide', 'confirm'), ('confirm', 'finished'),
        ('outer_decide', 'request_edit'), ('request_edit', 'edit'),
        ('finished', 'update'), ('update', 'finished'),
    ),
    params=(Parameter('--thread', 'Native trigger comment (optional)', required=False),),
)
