"""MAIN drafts and dispatches shipping features."""
from pathlib import Path
import shutil

from featssship import (DELEGATION_KEY, DISPATCH_KEY, check_repo, cli, config_ref, entry_command,
                       git, has_manual, link_config, request_config)
from github_issue import issue_link
from experiment import dispatch_experiment
from environment import prepare_environment
from thread import post
from batch import (configured, view, outer_owner, outer_view, refresh, request_changes,
                   save_progress, DRAFT_PROMPT, OUTER_PROMPT, REPLY_GUIDANCE)
from sop import FINISHED, Option, Parameter, State, Workflow

SOP_DISPLAY_NAME = 'multica-featssship-delegation'


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
            if request['type'] == 'exp':
                dispatch_experiment(context, request, item, index)
            else:
                dispatch_item(context, request, item, index)
            item.pop('branch_base', None)
            item.pop('remote_reserved', None)
        except ValueError as error:
            failures.append('issues[' + str(index) + '] ' + request['name'] + ': ' + str(error))
    if failures:
        save_progress(context)
        message = ('Dispatch incomplete. Preserve this approved batch and its child/worktree checkpoints. '
                   'Diagnose the errors below; for a connection failure check connectivity and retry confirm once. '
                   'Fetch remote main before preparing any remaining branch; do not reset existing feature work, '
                   'replay approval or create duplicate children. If still blocked, report the exact blocker.\n\n' +
                   '\n'.join(failures))
        if not record.get('recovery_requested'):
            post(context, '[@MAIN](mention://agent/' + context['main']['assignee_id'] + ') ' + message)
            record['recovery_requested'] = True
            save_progress(context)
        raise ValueError(message)
    cli('issue', 'metadata', 'delete', context['issue_id'], '--key', DISPATCH_KEY)


def dispatch_item(context, request, record, index):
    if record.get('issue_id'):
        child = cli('issue', 'get', record['issue_id'])
        if config_ref(child, DELEGATION_KEY) and child['status'] != 'backlog':
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
    prepare_environment(repo, worktree)
    skill = Path('.agents/skills/multica-featssship-develop-review')
    if not (worktree / skill).exists():
        shutil.copytree(repo / skill, worktree / skill,
                        ignore=shutil.ignore_patterns('.state', '__pycache__', '.errors'))
    if request['manual'] and not record.get('remote_reserved'):
        remote = git(repo, 'ls-remote', 'origin', ref).split()
        if remote and remote[0] != record['branch_base']:
            raise ValueError('Feature branch is already claimed: ' + branch)
        if not remote:
            try:
                git(repo, 'push', '--force-with-lease=' + ref + ':', 'origin', record['branch_base'] + ':' + ref)
            except ValueError as error:
                raise ValueError('Delegator: reconcile freshly fetched remote main and the target repository push policy, '
                                 'then retry this saved dispatch. Preserve the child and worktree; do not bypass hooks. ' + str(error)) from error
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
                   '\n\nBefore dependency changes/npm install, unlink a linked node_modules and run npm ci --include=dev for a private install. Never mutate the shared snapshot. Detach linked .env before branch-specific edits.' +
                   '\n\nUse the prepared feature worktree: ' + str(worktree) + '\n\n' +
                   entry_command('multica-featssship-develop-review'))
    cli('issue', 'update', child['id'], '--description-stdin', '--no-start', input=description)
    if child['status'] == 'backlog':
        cli('issue', 'status', child['id'], 'todo')


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
