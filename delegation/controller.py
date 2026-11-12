"""MAIN dispatches one human-approved JSON batch and resumes each child."""
import json
from pathlib import Path
import uuid
import tempfile

from common import DELEGATION_KEY, DISPATCH_KEY, attachment, check_repo, cli, config_ref, delegation_config, download_config, entry_command, git, has_manual, link_config, read_config, request_config, repo_root, write_config
from github_issue import issue_link, mirror_title
from sop import FINISHED, Option, Parameter, State, Workflow

FIELDS = {**dict.fromkeys(('name', 'request', 'direction', 'title', 'scope', 'question', 'github_issue', 'branch', 'parent_branch'), str),
          'manual': bool, 'sandbox': dict, 'questions': list}
WAIT_OUTER = 'do not call SoP and end this turn if no outer confirmation or edition instruction.'
PROMPT = ('Read current sub-issues list delegation config <file path>, edit JSON offline and upload '
          'the version via refresh --config-file PATH. ' + WAIT_OUTER)


def save_progress(context):
    cli('issue', 'metadata', 'set', context['issue_id'], '--key', DISPATCH_KEY,
        '--value', json.dumps(context['record']), '--type', 'string')


def publish(batch, context):
    envelope = {'source': config_ref(context['main']), 'main_issue_id': context['issue_id'],
                'dispatch_thread': context['record']['thread']}
    if (not isinstance(batch, dict) or set(batch) - {'issues', *envelope}
            or not isinstance(batch.get('issues'), list) or not batch['issues']
            or any(key in batch and batch[key] != value for key, value in envelope.items())):
        raise ValueError('Use {"issues": [{...}]} and keep source/owner/thread references unchanged.')
    if any(not isinstance(item, dict) or set(item) - set(FIELDS)
           or any(not isinstance(value, FIELDS[key]) for key, value in item.items()) for item in batch['issues']):
        raise ValueError('Each issues item accepts typed request fields: ' + ', '.join(FIELDS))
    for item in batch['issues']:
        item.setdefault('manual', has_manual(context['main']) or context['installed'].get('manual', False))
    config = delegation_config(context['installed'], batch, **envelope)
    row = write_config(context['reference'], config, context['args'].thread or envelope['dispatch_thread'], 'Config refreshed. Confirm or edit further ?')
    context['record'] = {'thread': envelope['dispatch_thread'], 'draft_comment_id': row['id'],
                         'draft_attachment_id': attachment(context['reference'])['id']}
    save_progress(context)


def configured(context):
    main, args = cli('issue', 'get', context['issue_id']), context['args']
    source = config_ref(main)
    if not source or main['workspace_id'] != context['workspace_id'] or main['assignee_id'] != context['agent_id']:
        raise context['error']('wrong_agent', 'Use the configured MAIN and its native assignee.')
    context.update(main=main, installed=read_config(source), reference=config_ref(main, DELEGATION_KEY),
                   record=json.loads(main.get('metadata', {}).get(DISPATCH_KEY, '{}')))
    if args.config is not None or not context['reference']:
        if context['reference'] and not (context['record'].get('dispatched') and args.thread and args.thread != context['record']['thread']):
            raise ValueError('Use refresh; a new batch needs a new --thread after full dispatch.')
        if not args.thread:
            raise ValueError('Start with --thread <original MAIN request comment>.')
        batch = json.loads(args.config) if args.config is not None else {'issues': [{}]}
        context.update(record={'thread': args.thread}, reference={
            'issue_id': main['id'], 'filename': 'featssship.delegation-' + str(uuid.uuid4()) + '.json'})
        publish(batch, context)
        link_config(main['id'], context['reference'], DELEGATION_KEY)
        args.config, context['argv'] = None, []  # Recalls read the document, never the initial JSON.
    path = download_config(context['reference'], tempfile.mkdtemp(prefix='featssship-delegation-'))
    context.update(config=json.loads(path.read_text()), config_path=str(path),
                   revision=attachment(context['reference'])['id'])


def view(context):
    return {'instruction': PROMPT.replace('<file path>', context['config_path'])}


def refresh(args, context):
    """```dot
    digraph refresh { node [shape=box]; read [label="Read offline JSON and validate issues"];
        upload [label="Replace attachment; clear approval"]; read -> upload; }
    ```"""
    if any(item.get('issue_id') for item in context['record'].get('items', [])):
        raise ValueError('Children exist; resume dispatch instead of refreshing this batch.')
    publish(json.loads(Path(args.config_file).read_text()), context)
    context['argv'] = []
    configured(context)


def dispatch(args, context):
    """```dot
    digraph dispatch { gate [label="Verify original human approval of current batch"];
        items [label="Create/resume children and branches; skip successes"]; report [label="All dispatched: finish; partial failures: report and stay grilling"];
        gate -> items -> report; }
    ```"""
    record, config = context['record'], context['config']
    if record['draft_attachment_id'] != context['revision']:
        raise context['error']('invalid_input', 'Refresh and obtain human approval of the current batch first.')
    if not record.get('approval_comment_id'):
        rows = cli('issue', 'comment', 'list', context['issue_id'], '--thread', record['draft_comment_id'], '--tail', '30')
        draft = next((row for row in rows if row['id'] == record['draft_comment_id']), None)
        human = next((row for row in reversed(rows)
                      if row['id'] == args.thread or (not args.thread and row.get('author_type') == 'member')), None)
        if (not draft or not human or human.get('author_type') != 'member'
                or rows.index(human) <= rows.index(draft)):
            raise context['error']('invalid_input', 'The human must confirm or accept the current batch draft in its thread.')
        record['approval_comment_id'] = human['id']
        save_progress(context)
    batch = [request_config(config, context['installed'], index=i) for i in range(len(config['issues']))]
    for index, request in enumerate(batch):
        missing = [key for key in ('name', 'request', 'direction', 'scope', 'question') if not (request.get(key) or '').strip()]
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
    record['dispatched'] = all(item.get('dispatched') for item in progress)
    save_progress(context)
    children = [item['issue_id'] for item in progress if item.get('dispatched')]
    return {'accepted': record['dispatched'], 'instruction':
            'Dispatched ' + str(len(children)) + '/' + str(len(batch)) + ': ' + ', '.join(children) +
            ('. Retry unfinished items.\n' + '\n'.join(failures) if failures else '; end this turn.')}


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
    url = issue_link(title, request.get('github_issue'))
    if url:
        title = mirror_title(title, url)
    if not record.get('issue_id'):
        child = cli('issue', 'create', '--title', title, '--description-stdin', '--parent', context['issue_id'],
                    '--project', context['main']['project_id'], '--assignee-id', context['installed']['installed_developer_id'],
                    '--status', 'backlog', input=request['request'])
        record['issue_id'] = child['id']
        save_progress(context)
    child = cli('issue', 'get', record['issue_id'])
    repo = repo_root()
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
    description = (request['request'] + '\n\nScope: ' + request['scope'] + '\n\nAcceptance: ' + request['question'] +
                   '\n\nUse the prepared feature worktree: ' + str(worktree) + '\n\nFollow the verification guidance in the project description.\n\n' +
                   entry_command('multica-featssship-develop-review') + '\n\nMAIN selected branch: ' + branch +
                   '. Developer and Reviewer use this existing branch in the shared issue folder from the start; '
                   'do not create a review checkout or switch branches.')
    cli('issue', 'update', child['id'], '--description-stdin', '--no-start', input=description)
    if child['status'] == 'backlog':
        cli('issue', 'status', child['id'], 'todo')
    record['dispatched'] = True
    save_progress(context)


workflow = Workflow(
    State('grilling', PROMPT, initial=True, precheck=configured, view=view, options=(
        Option('refresh', 'grilling', 'Validate and upload the whole offline JSON; clear approval.', refresh,
               params=(Parameter('--config-file', 'Path to the complete batch JSON'),)),
        Option('dispatch', FINISHED, 'Check human approval; dispatch all or stay grilling to retry.', dispatch),
    )),
    params=(Parameter('--thread', 'Native trigger UUID; original request when starting a batch', required=False),
            Parameter('--config', 'Initial {"issues": [{}]} JSON; omit to resume', required=False)),
)
