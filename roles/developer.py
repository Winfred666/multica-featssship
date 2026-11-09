"""Developer implements, requests independent review, and integrates approval."""
import fcntl
from pathlib import Path
import tempfile

from common import (block, check_repo, clean, cli, comment, current, entry_command,
                    exclude_local, feature, git, has_manual, human_accepts, latest,
                    mention, reply_parent, repo_root, test)
from commit_report import commit_report
from github_issue import close_issue, issue_link
from packages import compile_review
from sop import Option, Parameter, State, Workflow


def observed(context):
    issue, binding = feature(context)
    if context['args'].thread:
        context['state']['reply_parent'] = context['args'].thread
    context.update(issue=issue, binding=binding, observed=current(binding))
    return binding


def view(context):
    submission, _, review, _, _, _ = context['observed']
    return {'data': {'binding': context['binding'], 'submission': submission, 'review': review}}


def resume(args, context):
    submission, _, review, _, rows, _ = context['observed']
    result, _ = latest(rows, 'result')
    integrated, _ = latest(rows, 'integration')
    if result:
        if context['issue']['status'] != 'in_review':
            cli('issue', 'status', context['binding']['issue_id'], 'in_review')
        return {'phase': 'finished', 'data': result}
    if integrated:
        return {'phase': 'integrate'}
    return {'phase': 'implement' if not submission or review and review['verdict'] == 'rework' else
            'integrate' if review and review['verdict'] == 'approved' else 'await_review'}


def prepare(args, context):
    binding = context['binding']
    repo = repo_root()
    check_repo(repo, binding)
    exclude_local(repo)
    clean(repo)
    git(repo, 'fetch', 'origin', 'main')
    branch = binding['branch']
    submission = context['observed'][0]
    # A fresh correction checkout leaves the earlier worktree's branch intact.
    if submission and git(repo, 'branch', '--show-current') != branch:
        branch += '-' + context['task_id']
    exists = git(repo, 'branch', '--list', branch)
    if exists:
        git(repo, 'switch', branch)
    else:
        remote = git(repo, 'ls-remote', '--heads', 'origin', binding['branch'])
        if remote:
            git(repo, 'fetch', 'origin', binding['branch'])
            git(repo, 'switch', '-c', branch, submission['commit'] if submission else 'FETCH_HEAD')
        else:
            git(repo, 'switch', '-c', branch, 'origin/main')
    if context['issue']['status'] != 'in_progress':
        cli('issue', 'status', binding['issue_id'], 'in_progress')
    return {'instruction': 'Correct, amend the feature commit and resubmit.' if submission else 'Implement, commit and submit.'}


def submit(args, context):
    binding = context['binding']
    repo = repo_root()
    check_repo(repo, binding)
    if git(repo, 'branch', '--show-current') not in (binding['branch'], binding['branch'] + '-' + context['task_id']):
        raise ValueError('Prepare and implement on the bound feature branch first.')
    clean(repo)
    commit = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'fetch', 'origin', '+refs/heads/main:refs/remotes/origin/main')
    if git(repo, 'rev-list', '--count', 'origin/main..' + commit) != '1':
        raise ValueError('Use one commit per feature; amend corrections before submitting.')
    evidence = test(repo, binding['test_command'])
    changes = commit_report(repo, commit=commit)
    submission, _, _, review_row, _, _ = context['observed']
    target = 'refs/heads/' + binding['branch']
    expected = submission['commit'] if submission else ''
    git(repo, 'push', '--force-with-lease=' + target + ':' + expected, 'origin', 'HEAD:' + target)
    name, _ = compile_review(binding, commit)
    data = {'commit': commit, 'summary': args.summary, 'answer': args.answer, 'test': evidence, 'changes': changes}
    row = comment(binding['issue_id'], mention(binding['reviewer_id']) +
                  ' Review this commit; approve or return corrections. ' + entry_command(name) +
                  '\n\n' + block('submission', data),
                  reply_parent(context, review_row['id'] if review_row else binding['thread_id']),
                  steer_agent=binding['reviewer_id'])
    return {'data': {'submission_id': row['id'], **data},
            'instruction': 'Review requested. End this turn; resume on Reviewer’s reply.'}


def poll(args, context):
    _, _, review, _, _, _ = context['observed']
    if not review:
        return {'accepted': False, 'instruction': 'Await Reviewer’s verdict; end this turn.'}
    return {'phase': 'implement' if review['verdict'] == 'rework' else 'integrate'}


def integration(args, context):
    binding = context['binding']
    submission, submit_row, review, review_row, rows, comments = context['observed']
    if not submission or not review or review['verdict'] != 'approved':
        raise ValueError('Integration requires the configured Reviewer’s approval of the latest submission.')
    commit = submission['commit']
    if review['commit'] != commit:
        raise ValueError('The approval does not name the submitted commit.')
    if has_manual(context['issue']) and not human_accepts(comments, commit):
        return {'accepted': False, 'instruction': 'Manual hold: a human must reply in this thread with\n' + block('accept', {'commit': commit})}
    repo = repo_root()
    check_repo(repo, binding)
    clean(repo)
    branch = git(repo, 'branch', '--show-current')
    if (branch == binding['branch'] or branch.startswith(binding['branch'] + '-')) and git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('The feature branch changed after approval. Submit it for fresh review.')
    # One host lock covers separate task-local Git databases; remote push also rejects races.
    remote_path = binding['repository'].replace('git@github.com:', 'https://github.com/').split('://')[-1].removesuffix('.git')
    lock = Path.home() / '.local' / 'state' / 'multica-featssship' / remote_path / 'integration.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('w') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'accepted': False, 'instruction': 'Integration busy; retry after it finishes.'}
        git(repo, 'fetch', 'origin', '+refs/heads/main:refs/remotes/origin/main', binding['branch'])
        head = git(repo, 'ls-remote', 'origin', 'refs/heads/' + binding['branch']).split()[0]
        if head != commit:
            raise ValueError('The feature branch changed after approval. Submit it for fresh review.')
        existing, _ = latest(rows, 'integration')
        if existing:
            integrated = existing
            git(repo, 'merge-base', '--is-ancestor', integrated['revision'], 'origin/main')
        else:
            parent = repo / '.multica' / 'featssship' / 'integration'
            parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=parent) as temporary:
                checkout = Path(temporary) / 'checkout'
                git(repo, 'worktree', 'add', '--detach', str(checkout), 'origin/main')
                try:
                    try:
                        git(checkout, 'merge', '--no-edit', commit)
                        evidence = test(checkout, binding['test_command'])
                    except ValueError as error:
                        # The disposable checkout is removed; the feature branch stays intact.
                        data = {'commit': commit, 'submission_id': submit_row['id'], 'finding': str(error)}
                        comment(binding['issue_id'], mention(binding['developer_id']) +
                                ' Fix integration and resubmit.\n\n' + block('integration-rework', data),
                                reply_parent(context, review_row['id']))
                        return {'phase': 'implement', 'instruction': 'Fix integration against current main and resubmit.', 'data': data}
                    revision = git(checkout, 'rev-parse', 'HEAD')
                    git(checkout, 'push', 'origin', 'HEAD:refs/heads/main')
                    integrated = {'revision': revision, 'commit': commit, 'review_id': review_row['id'], 'verdict': 'approved',
                                  'answer': review['answer'], 'test': evidence, 'summary': submission['summary'],
                                  'changes': submission.get('changes') or commit_report(repo, commit=commit)}
                    comment(binding['issue_id'], block('integration', integrated), reply_parent(context, review_row['id']))
                finally:
                    git(repo, 'worktree', 'remove', '--force', str(checkout))
        url = binding.get('github_issue') or issue_link(context['issue']['title'])
        if url:
            close_issue(url, binding, integrated, submission)
            integrated = {**integrated, 'github_issue': url}
        # A receipt in MAIN makes a retry after an uncertain write observable.
        main_rows = cli('issue', 'comment', 'list', binding['root_issue_id'], '--thread', binding['main_thread_id'], '--tail', '30')
        from common import unpack
        receipt = next((row for row in main_rows if row.get('author_id') == binding['developer_id'] and
                        (unpack(row.get('content', ''), 'result') or {}).get('issue_id') == binding['issue_id']), None)
        if not receipt:
            receipt = comment(binding['root_issue_id'], mention(binding['main_id']) +
                              ' [Feature](mention://issue/' + binding['issue_id'] + ') integrated.\n\n' +
                              block('result', {'issue_id': binding['issue_id'], **integrated}),
                              binding['main_thread_id'], steer_agent=binding['main_id'])
        comment(binding['issue_id'], block('result', {'main_comment_id': receipt['id'], **integrated}), reply_parent(context, review_row['id']))
        cli('issue', 'status', binding['issue_id'], 'in_review')
    return {'data': integrated}


workflow = Workflow(
    State('resume', 'Resume from the latest submission and verdict.', initial=True,
          precheck=observed, view=view, options=(Option('resume', 'implement', 'Resume from native evidence.', resume),)),
    State('implement', 'Implement or amend the feature commit, then submit.', precheck=observed, view=view, options=(
        Option('prepare', 'implement', 'Prepare the feature branch in this repository.', prepare),
        Option('submit', 'await_review', 'Test, push and steer Reviewer with the inline report.', submit, params=(
            Parameter('--summary', 'Outcome, technical approach and necessary reference links or artifacts'),
            Parameter('--answer', 'Optional acceptance answer', required=False),)),)),
    State('await_review', 'Await Reviewer’s verdict; end this turn.', precheck=observed, view=view, options=(
        Option('check', 'integrate', 'Read the current verdict.', poll),)),
    State('integrate', 'Integrate the approved commit and report to MAIN.', precheck=observed, view=view, options=(
        Option('integrate', 'finished', 'Merge, test, push and report.', integration),)),
    State('finished', 'Delivered to MAIN; end this turn.', final=True),
    params=(Parameter('--thread', 'Native triggering comment UUID for this task', required=False),),
)
