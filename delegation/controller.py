"""MAIN drafts a batch; outer confirms dispatch or requests changes."""
import json
from pathlib import Path
import shutil
import uuid
import tempfile

from featssship import DELEGATION_KEY, DISPATCH_KEY, attachment, check_repo, cli, config_ref, delegation_config, download_config, entry_command, git, has_manual, link_config, read_config, request_config, wake_agent, write_config
from github_issue import issue_link
from sop import FINISHED, Option, Parameter, State, Workflow

SOP_DISPLAY_NAME = 'multica-featssship-delegation'

FIELDS = {**dict.fromkeys(('name', 'request', 'direction', 'title', 'scope', 'github_issue', 'branch', 'parent_branch', 'developer_id'), str),
          'manual': bool, 'sandbox': dict, 'questions': list}
DRAFT_PROMPT = ('Read the batch JSON at <file path>, apply the request offline, then publish '
          'with refresh --config-file PATH.')
OUTER_PROMPT = 'Confirm or edit.'
REPLY_GUIDANCE = 'Briefly explain the batch changes in this thread, then end this turn.'


def save_progress(context):
    cli('issue', 'metadata', 'set', context['issue_id'], '--key', DISPATCH_KEY,
        '--value', json.dumps(context['record']), '--type', 'string')


def batch_config(batch, context):
    envelope = {'source': config_ref(context['main']), 'main_issue_id': context['issue_id'],
                'dispatch_thread': context['record']['thread']}
    if (not isinstance(batch, dict) or set(batch) - {'issues', *envelope}
            or not isinstance(batch.get('issues'), list) or not batch['issues']
            or any(key in batch and batch[key] != value for key, value in envelope.items())):
        raise ValueError('Use {"issues": [{...}]} and keep source/owner/thread references unchanged.')
    if any(not isinstance(item, dict) or set(item) - set(FIELDS)
           or any(not isinstance(value, FIELDS[key]) for key, value in item.items()) for item in batch['issues']):
        raise ValueError('Each issues item accepts typed request fields: ' + ', '.join(FIELDS))
    return delegation_config(context['installed'], batch, **envelope)


def publish(batch, context):
    config = batch_config(batch, context)
    write_config(context['reference'], config, context['state']['reply_parent'])
    link_config(context['issue_id'], context['reference'], DELEGATION_KEY)
    context['record'] = {'thread': config['dispatch_thread'],
                         'draft_attachment_id': attachment(context['reference'])['id']}
    save_progress(context)


def configured(context):
    main, args = cli('issue', 'get', context['issue_id']), context['args']
    source = config_ref(main)
    if not source or main['workspace_id'] != context['workspace_id'] or main['assignee_id'] != context['agent_id']:
        raise context['error']('wrong_agent', 'Use the configured MAIN and its native assignee.')
    context.update(main=main, reference=config_ref(main, DELEGATION_KEY),
                   record=json.loads(main.get('metadata', {}).get(DISPATCH_KEY, '{}')))
    state = context['state']
    context['installed'] = read_config(source)
    if args.thread:
        state['reply_parent'] = args.thread
    if (args.config is not None or not context['record']) and not state.get('draft'):
        if context['record']:
            raise ValueError('Use refresh to edit the current batch.')
        if not args.thread:
            raise ValueError('Start with --thread <original MAIN request comment>.')
        batch = json.loads(args.config) if args.config is not None else {'issues': [{}]}
        context.update(record={'thread': args.thread}, reference={
            'issue_id': main['id'], 'filename': 'featssship.delegation-' + str(uuid.uuid4()) + '.json'})
        path = Path(tempfile.mkdtemp(prefix='featssship-delegation-')) / context['reference']['filename']
        path.write_text(json.dumps(batch_config(batch, context), indent=2) + '\n')
        state['draft'] = {'thread': args.thread, 'reference': context['reference'], 'path': str(path)}
        args.config, context['argv'] = None, []
    if draft := state.get('draft'):
        context.update(record={'thread': draft['thread']}, reference=draft['reference'])
        path = Path(draft['path'])
    else:
        path = download_config(context['reference'], tempfile.mkdtemp(prefix='featssship-delegation-'))
        context['revision'] = attachment(context['reference'])['id']
    context.update(config=json.loads(path.read_text()), config_path=str(path))


def view(context):
    return {'instruction': DRAFT_PROMPT.replace('<file path>', context['config_path']) +
            ('\n\nRequested changes: ' + context['state']['change_request']
             if context['state'].get('change_request') else '')}


def outer_owner(context):
    return {'issue_id': context['issue_id'], 'thread': context['state']['reply_parent'],
            'id': None, 'content': '/note'}


def outer_view(context):
    row = attachment(context['reference'])
    return {'instruction': OUTER_PROMPT + '\n\n[' + row['filename'] + '](' + row['markdown_url'] + ').'}


def request_changes(args, context):
    if any(item.get('issue_id') for item in context['record'].get('items', [])):
        raise ValueError('Children exist; resume dispatch instead of editing this batch.')
    context['state']['change_request'] = args.change_request
    wake_agent(context, context['main']['assignee_id'], 'Batch changes requested: ' + args.change_request)


def refresh(args, context):
    """```dot
    digraph refresh { node [shape=box]; read [label="Read offline JSON and validate issues"];
        upload [label="Publish batch attachment"]; read -> upload; }
    ```"""
    if any(item.get('issue_id') for item in context['record'].get('items', [])):
        raise ValueError('Children exist; resume dispatch instead of refreshing this batch.')
    publish(json.loads(Path(args.config_file).read_text()), context)
    context['state'].pop('draft', None)
    context['state'].pop('change_request', None)
    context['argv'] = []
    configured(context)
    return {'this_round_reply_guidance': REPLY_GUIDANCE}


def dispatch(args, context):
    """```dot
    digraph dispatch { gate [label="Validate current batch revision and requests"];
        items [label="Create/resume children and branches; skip successes"]; report [label="All dispatched: finish; partial failures: report and allow retry"];
        gate -> items -> report; }
    ```"""
    record, config = context['record'], context['config']
    if record['draft_attachment_id'] != context['revision']:
        raise context['error']('invalid_input', 'Refresh the current batch before dispatch.')
    batch = [request_config(config, context['installed'], index=i) for i in range(len(config['issues']))]
    for index, request in enumerate(batch):
        missing = [key for key in ('name', 'request', 'direction', 'scope') if not (request.get(key) or '').strip()]
        if missing or request['direction'] not in {d['name'] for d in context['installed']['directions']}:
            raise ValueError('issues[' + str(index) + '] needs an installed direction and: ' + ', '.join(missing))
    progress = record.setdefault('items', [{} for _ in batch])
    failures = []
    for index, (request, item) in enumerate(zip(batch, progress)):
        try:
            dispatch_item(context, request, item, index)
            item.pop('branch_base', None)
            item.pop('remote_reserved', None)
        except ValueError as error:
            failures.append('issues[' + str(index) + '] ' + request['name'] + ': ' + str(error))
    if failures:
        save_progress(context)
        raise ValueError('\n'.join(failures))
    cli('issue', 'metadata', 'delete', context['issue_id'], '--key', DISPATCH_KEY)


def dispatch_item(context, request, record, index):
    if record.get('dispatched'):
        return
    if record.get('issue_id'):
        child = cli('issue', 'get', record['issue_id'])
        if config_ref(child, DELEGATION_KEY) and child['status'] != 'backlog':
            record['dispatched'] = True
            save_progress(context)
            return
    branch = request['branch']
    title = request.get('title') or request['name']
    url = issue_link(request.get('github_issue'))
    if url:
        title = f'[{title}]({url})'
    if not record.get('issue_id'):
        child = cli('issue', 'create', '--title', title, '--description-stdin', '--parent', context['issue_id'],
                    '--project', context['main']['project_id'], '--assignee-id', request['developer_id'],
                    '--status', 'backlog', input=request['request'])
        record['issue_id'] = child['id']
        save_progress(context)
    child = cli('issue', 'get', record['issue_id'])
    repo = Path(git(Path(__file__).resolve().parent, 'rev-parse', '--show-toplevel')).resolve()
    check_repo(repo, context['installed'])
    parent_branch = request['parent_branch']
    ref = 'refs/heads/' + branch
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    worktree = common / 'featsship' / child['id']
    if not record.get('branch_base'):
        git(repo, 'fetch', 'origin', parent_branch)
        base = git(repo, 'rev-parse', 'FETCH_HEAD^{commit}')
        if not worktree.exists():
            if git(repo, 'for-each-ref', '--format=%(refname)', ref):
                raise ValueError('Feature branch is already claimed: ' + branch)
            git(repo, 'worktree', 'add', '-b', branch, str(worktree), base)
        if git(worktree, 'branch', '--show-current') != branch:
            raise ValueError('The feature worktree belongs to another branch.')
        record['branch_base'] = git(worktree, 'rev-parse', 'HEAD')
        save_progress(context)
    skill = Path('.agents/skills/multica-featssship-develop-review')
    if not (worktree / skill).exists():
        shutil.copytree(repo / skill, worktree / skill,
                        ignore=shutil.ignore_patterns('.state', '__pycache__', '.errors'))
    if request['manual'] and not record.get('remote_reserved'):
        if git(repo, 'ls-remote', 'origin', ref):
            raise ValueError('Feature branch is already claimed: ' + branch)
        git(repo, 'push', '--force-with-lease=' + ref + ':', 'origin', record['branch_base'] + ':' + ref)
        record['remote_reserved'] = True
        save_progress(context)
    cli('issue', 'metadata', 'set', child['id'], '--key', 'git_base_commit',
        '--value', record['branch_base'], '--type', 'string')
    labels = cli('label', 'list')
    labels = labels.get('labels', []) if isinstance(labels, dict) else labels
    cli('issue', 'label', 'add', child['id'], next(label['id'] for label in labels if label['name'] == 'dev'))
    if request['manual'] and not has_manual(child):
        label = next((label for label in labels if label['name'] == 'manual'), None)
        label = label or cli('label', 'create', '--name', 'manual', '--color', '#64748b')
        cli('issue', 'label', 'add', child['id'], label['id'])
    link_config(child['id'], {**context['reference'], 'index': index}, DELEGATION_KEY)
    description = (request['request'] + '\n\nScope: ' + request['scope'] +
                   '\n\nTest: `' + request['test_command'] + '`' +
                   '\n\nUse the prepared feature worktree: ' + str(worktree) + '\n\n' +
                   entry_command('multica-featssship-develop-review'))
    cli('issue', 'update', child['id'], '--description-stdin', '--no-start', input=description)
    if child['status'] == 'backlog':
        cli('issue', 'status', child['id'], 'todo')
    record['dispatched'] = True
    save_progress(context)


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
