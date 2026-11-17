"""MAIN dispatches experiment review, never shipping or integration."""
from pathlib import Path
from featssship import DELEGATION_KEY, DISPATCH_KEY, cli, comment, git, link_config, request_config
from batch import configured, view, outer_owner, outer_view, refresh, request_changes, save_progress, DRAFT_PROMPT, OUTER_PROMPT, REPLY_GUIDANCE
from sop import FINISHED, Option, Parameter, State, Workflow

SOP_DISPLAY_NAME = 'multica-featssship-split-delegation'
FINISHED_INSTRUCTION = 'End this turn silently.'


def exp_label(issue_id):
    labels = cli('label', 'list')
    labels = labels.get('labels', []) if isinstance(labels, dict) else labels
    label = next((row for row in labels if row['name'] == 'exp'), None)
    label = label or cli('label', 'create', '--name', 'exp', '--color', '#8b5cf6')
    cli('issue', 'label', 'add', issue_id, label['id'])


def dispatch(args, context):
    """```dot
    digraph dispatch { validate -> reviewer_children -> start_reviewers; }
    ```"""
    record, config = context['record'], context['config']
    if record['draft_attachment_id'] != context['revision']:
        raise ValueError('Refresh the current batch before dispatch.')
    batch = [request_config(config, context['installed'], index=i) for i in range(len(config['issues']))]
    for request in batch:
        if any(not request.get(key) for key in ('name', 'request', 'direction', 'scope')):
            raise ValueError('Every experiment needs name, request, direction and scope.')
        if request['direction'] not in {d['name'] for d in context['installed']['directions']}:
            raise ValueError('Choose an installed direction.')
    progress = record.setdefault('items', [{} for _ in batch])
    for index, (request, item) in enumerate(zip(batch, progress)):
        if item.get('dispatched'):
            continue
        if not item.get('issue_id'):
            child = cli('issue', 'create', '--title', request.get('title') or request['name'],
                        '--description-stdin', '--parent', context['issue_id'],
                        '--project', context['main']['project_id'],
                        '--assignee-id', context['installed']['installed_reviewer_id'],
                        '--status', 'backlog', input=request['request'])
            item['issue_id'] = child['id']
            save_progress(context)
        exp_label(item['issue_id'])
        link_config(item['issue_id'], {**context['reference'], 'index': index}, DELEGATION_KEY)
        if not item.get('review_thread'):
            item['review_thread'] = comment(item['issue_id'], '/note Experiment review thread.')['id']
            save_progress(context)
        description = (request['request'] + '\n\nScope: ' + request['scope'] + '\n\nVariant: ' + request['name'] +
                       '\n\nReviewer owns this experiment. From ' + str(Path(git(Path(__file__).resolve().parent, 'rev-parse', '--show-toplevel')).resolve()) +
                       ', run `multica sop run multica-featssship-devrev-split --thread ' + item['review_thread'] + '`. '
                       'No integration or push-to-main. Hidden inputs stay outside shared settings.\n\n' +
                       Path(__file__).with_name('PROJECT.md').read_text().strip())
        cli('issue', 'update', item['issue_id'], '--description-stdin', '--no-start', input=description)
        if cli('issue', 'get', item['issue_id'])['status'] == 'backlog':
            cli('issue', 'status', item['issue_id'], 'todo')
        item['dispatched'] = True
        save_progress(context)
    cli('issue', 'metadata', 'delete', context['issue_id'], '--key', DISPATCH_KEY)


workflow = Workflow(
    State('edit', DRAFT_PROMPT, initial=True, precheck=configured, view=view, preview=DRAFT_PROMPT,
          owner=lambda context: {'id': context['main']['assignee_id'], 'name': 'MAIN'}),
    State('outer_decide', OUTER_PROMPT, precheck=configured, view=outer_view,
          preview=OUTER_PROMPT, owner=outer_owner),
    Option('refresh', prompt='Validate and publish the whole offline batch for outer confirmation.', action=refresh,
           this_round_reply_guidance_preview=REPLY_GUIDANCE,
           params=(Parameter('--config-file', 'Path to the complete batch JSON'),)),
    Option('confirm', prompt='confirm', action=dispatch),
    Option('request_changes', prompt='edit', action=request_changes,
           params=(Parameter('--change-request', 'Changes to apply to the batch'),)),
    edges=(('edit', 'refresh'), ('refresh', 'outer_decide'),
           ('outer_decide', 'confirm'), ('confirm', FINISHED),
           ('outer_decide', 'request_changes'), ('request_changes', 'edit')),
    params=(Parameter('--thread', 'Native trigger UUID; original request when starting a batch', required=False),
            Parameter('--config', 'Initial {"issues": [{}]} JSON; omit to resume', required=False)),
)
