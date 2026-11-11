"""MAIN edits one metadata config, dispatches it, and receives the result."""
import json
from pathlib import Path

from common import PROCESS_KEY, WAIT_OUTER, block, check_repo, cli, comment, entry_command, feature_branch, git, has_manual, installation_config, installer_config, merge_patch, process_config, repo_root, save_config
from github_issue import issue_link, mirror_title
from sop import Option, Parameter, State, Workflow

DELEGATION_KEY = 'featssship.delegation'
FIELDS = ('name', 'request', 'direction', 'title', 'scope', 'question', 'github_issue', 'manual')
PROMPT = ('Align the config with this request, keeping choices that already fit. '
          'If context leaves a field uncertain, ask the human one self-contained question and end this turn. '
          'Use edit to record the answer; otherwise dispatch. If waiting for an outer reply: ' + WAIT_OUTER + ' ')
COMMENTS = ('name is a short kebab-case feature name; direction selects installed defaults for scope, '
            'question and branch prefix. Verification guidance comes from the project description. title defaults to name. '
            'manual is a boolean; true publishes a remote feature branch and waits for superior approval. github_issue is an optional source URL. Config and dispatch checkpoints stay in MAIN metadata.')


def configured(context):
    main = cli('issue', 'get', context['issue_id'])
    process = process_config(main)
    if (not process or context['workspace_id'] != main['workspace_id']
            or context['agent_id'] != main['assignee_id']):
        context['state'] = {}
        raise context['error']('wrong_agent', 'Delegation belongs to MAIN and its native assignee.')
    record = context['state'].get('delegation', installation_config(main, DELEGATION_KEY))
    if record:
        record['config'].pop('test_command', None)
    context.update(main=main, process=process, installed=installer_config(main), record=record)
    if context['args'].config is not None:
        config = json.loads(context['args'].config)
        if not isinstance(config, dict):
            raise ValueError('--config must be a JSON object.')
        if not record or (record.get('dispatched') and context['args'].thread and context['args'].thread != record.get('thread')):
            record = {'config': config, 'thread': context['args'].thread}
            context['record'] = record
        elif config != record['config']:
            raise ValueError('Resume without --config and use edit; start a new request with a new --thread after dispatch.')
    record.setdefault('config', {})
    config = record['config']
    if set(config) - set(FIELDS) or any(not isinstance(value, bool if key == 'manual' else str) for key, value in config.items()):
        raise ValueError('manual must be boolean; other config fields must be strings: ' + ', '.join(FIELDS))
    context['state']['delegation'] = record
    if context['args'].thread:
        context['state']['reply_parent'] = context['args'].thread


def request_config(context):
    config = dict(context['record']['config'])
    config.setdefault('manual', has_manual(context['main']) or context['process'].get('manual', False))
    directions = context['process']['directions']
    if len(directions) == 1:
        config.setdefault('direction', next(iter(directions)))
    selected = directions.get(config.get('direction'))
    if selected:
        init = next(d for d in context['installed']['directions'] if d['name'] == config['direction'])
        for key, value in (('scope', init['scope']), ('question', selected['questions'][0])):
            config.setdefault(key, value)
    return config


def view(context):
    return {'instruction': PROMPT + COMMENTS + '\n\nCurrent config:\n' + json.dumps(request_config(context), indent=2)}


def edit(args, context):
    """```dot
    digraph edit { node [shape=box]; patch [label="Merge patch into request config"];
        save [label="Save MAIN metadata and comment config; stay in grilling"];
        patch -> save; }
    ```"""
    record = context['record']
    if record.get('issue_id'):
        raise ValueError('This request is already dispatched; start a new request with --thread and --config.')
    patch = json.loads(args.patch)
    if not isinstance(patch, dict) or set(patch) - set(FIELDS) or any(value is not None and not isinstance(value, bool if key == 'manual' else str) for key, value in patch.items()):
        raise ValueError('--patch expects manual as boolean, other fields as strings, or null: ' + ', '.join(FIELDS))
    record['config'] = merge_patch(record['config'], patch)
    save_config(context['issue_id'], record, DELEGATION_KEY)
    comment(context['issue_id'], block('delegation-config', request_config(context)),
            args.thread or context['state'].get('reply_parent') or record.get('thread'))


def dispatch(args, context):
    """```dot
    digraph dispatch { node [shape=box]; validate [label="Require complete config"];
        child [label="Create child once or resume saved dispatch"];
        publish [label="Prepare local worktree; remote branch only if manual"];
        start [label="Start Developer; retain config and checkpoint"];
        validate -> child -> publish -> start; }
    ```"""
    record, process = context['record'], context['process']
    request = request_config(context)
    if record.get('issue_id'):
        child = cli('issue', 'get', record['issue_id'])
        if process_config(child) and child['status'] != 'backlog':
            record['dispatched'] = True
            save_config(context['issue_id'], record, DELEGATION_KEY)
            return {'instruction': 'Already dispatched to ' + child['id'] + '; end this turn.'}
    missing = [key for key in ('name', 'request', 'direction', 'scope', 'question') if not request.get(key, '').strip()]
    if missing:
        return {'accepted': False, 'instruction': view(context)['instruction'] +
                '\n\nFill from context or ask one question about: ' + ', '.join(missing)}
    selected = process['directions'].get(request['direction'])
    if not selected:
        raise ValueError('Choose a configured direction: ' + ', '.join(process['directions']))
    branch = feature_branch(selected, request['name'])
    title = request.get('title') or request['name']
    url = issue_link(title, request.get('github_issue'))
    if url:
        title = mirror_title(title, url)
    if not record.get('issue_id'):
        child = cli('issue', 'create', '--title', title, '--description-stdin', '--parent', context['issue_id'],
                    '--project', context['main']['project_id'], '--assignee-id', context['installed']['installed_developer_id'],
                    '--status', 'backlog', input=request['request'])
        record['issue_id'] = child['id']
        save_config(context['issue_id'], record, DELEGATION_KEY)
    child = cli('issue', 'get', record['issue_id'])
    repo = repo_root()
    check_repo(repo, context['installed'])
    parent_branch = context['main'].get('metadata', {}).get('git_branch', 'main')
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
        save_config(context['issue_id'], record, DELEGATION_KEY)
    if request['manual'] and not record.get('remote_reserved'):
        if git(repo, 'ls-remote', 'origin', ref):
            raise ValueError('Feature branch is already claimed: ' + branch)
        git(repo, 'push', '--force-with-lease=' + ref + ':', 'origin', record['branch_base'] + ':' + ref)
        record['remote_reserved'] = True
        save_config(context['issue_id'], record, DELEGATION_KEY)
    for key, value in {'git_repository': context['installed']['repository'], 'git_branch': branch,
                       'git_parent_branch': parent_branch, 'git_base_commit': record['branch_base']}.items():
        cli('issue', 'metadata', 'set', child['id'], '--key', key, '--value', value, '--type', 'string')
    if request['manual'] and not has_manual(child):
        labels = cli('label', 'list')
        labels = labels.get('labels', []) if isinstance(labels, dict) else labels
        label = next((label for label in labels if label['name'] == 'manual'), None)
        label = label or cli('label', 'create', '--name', 'manual', '--color', '#64748b')
        cli('issue', 'label', 'add', child['id'], label['id'])
    child_process = {'questions': [request['question'], *[q for q in selected['questions'] if q != request['question']]],
                     'branch': branch, 'parent_branch': parent_branch, 'manual': request['manual'],
                     'main_issue_id': context['issue_id']}
    if 'sandbox' in process:
        child_process['sandbox'] = process['sandbox']
    save_config(child['id'], child_process, PROCESS_KEY)
    description = (request['request'] + '\n\nScope: ' + request['scope'] + '\n\nAcceptance: ' + request['question'] +
                   '\n\nUse the prepared feature worktree: ' + str(worktree) + '\n\nFollow the verification guidance in the project description.\n\n' +
                   entry_command('multica-featssship-develop-review') + '\n\nMAIN selected branch: ' + branch +
                   '. Developer and Reviewer use this existing branch in the shared issue folder from the start; '
                   'do not create a review checkout or switch branches.')
    cli('issue', 'update', child['id'], '--description-stdin', '--no-start', input=description)
    if child['status'] == 'backlog':
        cli('issue', 'status', child['id'], 'todo')
    record['dispatched'] = True
    save_config(context['issue_id'], record, DELEGATION_KEY)
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
