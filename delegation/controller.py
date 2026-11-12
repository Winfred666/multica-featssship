"""MAIN derives one shared delegation document and checkpoints its dispatch."""
import json
from pathlib import Path
import uuid

from common import DELEGATION_KEY, DISPATCH_KEY, WAIT_OUTER, check_repo, cli, config_ref, delegation_config, entry_command, git, has_manual, link_config, merge_patch, read_config, request_config, repo_root, write_config
from github_issue import issue_link, mirror_title
from sop import Option, Parameter, State, Workflow

CACHE_VIEW = False

FIELDS = {**dict.fromkeys(('name', 'request', 'direction', 'title', 'scope', 'question', 'github_issue', 'branch', 'parent_branch'), str),
          'manual': bool, 'sandbox': dict, 'questions': list}
PROMPT = ('Align the config with this request, keeping choices that already fit. '
          'If context leaves a field uncertain, ask the human one self-contained question and end this turn. '
          'Use edit to record the answer; otherwise dispatch. If waiting for an outer reply: ' + WAIT_OUTER + ' ')
COMMENTS = ('name is a short kebab-case feature name; direction selects installed defaults for scope, '
            'question and branch prefix. Verification guidance comes from the project description. title defaults to name. '
            'manual is a boolean; true publishes a remote feature branch and waits for superior approval. github_issue is an optional source URL. Configuration is an attachment; metadata retains its reference and dispatch progress.')


def save_progress(context):
    cli('issue', 'metadata', 'set', context['issue_id'], '--key', DISPATCH_KEY,
        '--value', json.dumps(context['record']), '--type', 'string')


def configured(context):
    main = cli('issue', 'get', context['issue_id'])
    source = config_ref(main)
    if (not source or context['workspace_id'] != main['workspace_id']
            or context['agent_id'] != main['assignee_id']):
        raise context['error']('wrong_agent', 'Delegation belongs to the configured MAIN and its native assignee.')
    installed = read_config(source)
    record = json.loads(main.get('metadata', {}).get(DISPATCH_KEY, '{}'))
    reference = config_ref(main, DELEGATION_KEY)
    context.update(main=main, installed=installed, record=record, reference=reference)
    args = context['args']
    if args.thread:
        context['state']['reply_parent'] = args.thread
    if args.config is not None:
        request = json.loads(args.config)
        if (not isinstance(request, dict) or set(request) - set(FIELDS)
                or any(not isinstance(value, FIELDS[key]) for key, value in request.items())):
            raise ValueError('--config expects request fields with their declared types: ' + ', '.join(FIELDS))
        if reference and not (record.get('dispatched') and args.thread and args.thread != record.get('thread')):
            raise ValueError('Resume without --config and use edit; a new request needs a new --thread after dispatch.')
    elif reference:
        context['config'] = request_config(read_config(reference), installed)
        return
    else:
        request = {}
    reference = {'issue_id': main['id'], 'filename': 'featssship.delegation-' + str(uuid.uuid4()) + '.json'}
    request.setdefault('manual', has_manual(main) or installed.get('manual', False))
    config = delegation_config(installed, request, source, main['id'])
    write_config(reference, config, args.thread, 'Edit or confirm.')
    link_config(main['id'], reference, DELEGATION_KEY)
    context.update(config=request_config(config, installed), reference=reference, record={'thread': args.thread})
    save_progress(context)
    # Recovery resumes the saved document, never a JSON payload cached in SoP state.
    if '--config' in context['argv']:
        index = context['argv'].index('--config')
        del context['argv'][index:index + 2]
    args.config = None


def view(context):
    return {'instruction': PROMPT + COMMENTS + '\n\nRead the latest delegation attachment: ' + json.dumps(context['reference'])}


def edit(args, context):
    """```dot
    digraph edit { node [shape=box]; patch [label="Merge patch into delegation document"];
        save [label="Publish attachment revision; retain only its reference"];
        patch -> save; }
    ```"""
    if context['record'].get('issue_id'):
        raise ValueError('This request is already dispatched; start a new request with --thread and --config.')
    patch = json.loads(args.patch)
    if not isinstance(patch, dict) or set(patch) - set(FIELDS) or any(value is not None and not isinstance(value, FIELDS[key]) for key, value in patch.items()):
        raise ValueError('--patch expects request fields with their declared types, or null: ' + ', '.join(FIELDS))
    request = merge_patch({key: value for key, value in read_config(context['reference']).items() if key in FIELDS}, patch)
    context['config'] = delegation_config(context['installed'], request, config_ref(context['main']), context['issue_id'])
    write_config(context['reference'], context['config'], args.thread or context['state'].get('reply_parent'), 'Edit or confirm.')
    context['config'] = request_config(context['config'], context['installed'])
    args.patch = '{}'
    context['argv'] = ['edit', '--patch', '{}']


def dispatch(args, context):
    """```dot
    digraph dispatch { node [shape=box]; validate [label="Require complete config"];
        child [label="Create child once or resume saved dispatch"];
        publish [label="Prepare local worktree; remote branch only if manual"];
        start [label="Start Developer; retain document reference and checkpoint"];
        validate -> child -> publish -> start; }
    ```"""
    record, request = context['record'], context['config']
    if record.get('issue_id'):
        child = cli('issue', 'get', record['issue_id'])
        if config_ref(child, DELEGATION_KEY) and child['status'] != 'backlog':
            record['dispatched'] = True
            save_progress(context)
            return {'instruction': 'Already dispatched to ' + child['id'] + '; end this turn.'}
    missing = [key for key in ('name', 'request', 'direction', 'scope', 'question') if not (request.get(key) or '').strip()]
    if missing:
        return {'accepted': False, 'instruction': view(context)['instruction'] +
                '\n\nFill from context or ask one question about: ' + ', '.join(missing)}
    if not record.get('thread'):
        raise ValueError('Pass the original MAIN request comment with --thread before dispatch.')
    directions = context['installed']['directions']
    selected = next((d for d in directions if d['name'] == request['direction']), None)
    if not selected:
        raise ValueError('Choose a configured direction: ' + ', '.join(d['name'] for d in directions))
    if not record.get('issue_id'):
        document = {**read_config(context['reference']), 'direction': request['direction'],
                    'branch': request['branch'], 'dispatch_thread': record['thread']}
        write_config(context['reference'], document, args.thread or context['state'].get('reply_parent'))
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
    if request['manual'] and not has_manual(child):
        labels = cli('label', 'list')
        labels = labels.get('labels', []) if isinstance(labels, dict) else labels
        label = next((label for label in labels if label['name'] == 'manual'), None)
        label = label or cli('label', 'create', '--name', 'manual', '--color', '#64748b')
        cli('issue', 'label', 'add', child['id'], label['id'])
    link_config(child['id'], context['reference'], DELEGATION_KEY)
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
    return {'instruction': 'Dispatched to ' + child['id'] + '; end this turn.'}


workflow = Workflow(
    State('grilling', PROMPT, initial=True, precheck=configured, view=view, options=(
        Option('edit', 'grilling', 'Update only the settings that need changing.', edit,
               params=(Parameter('--patch', 'JSON merge patch for the request config'),)),
        Option('dispatch', 'finished', 'Dispatch the settled config; retries resume the same child.', dispatch),
    )),
    State('finished', 'MAIN waits for one verified result from the feature issue.', final=True),
    params=(Parameter('--thread', 'Native request/trigger comment UUID; a new request needs a new thread', required=False),
            Parameter('--config', 'Initial request config JSON; omit when resuming or editing', required=False)),
)
