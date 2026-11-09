"""One issue-owned shipping flow; Developer edits and Reviewer judges."""
from pathlib import Path
import tempfile

from common import (block, check_repo, clean, cli, comment, current, entry_command,
                    exclude_local, feature, git, has_manual, human_accepts, latest,
                    mention, reply_parent, repo_root, test)
from commit_report import commit_report
from github_issue import close_issue, issue_link
from sop import Branch, Completed, Option, Parameter, State, Workflow


def observed(context):
    role = 'reviewer' if context['phase'] == 'review' else 'developer'
    issue, binding = feature(context, role if 'result' not in context else None)
    if 'result' in context and context['prior_status'] != context['phase']:
        context['state'].pop('reply_parent', None)
    elif context['args'].thread:
        context['state']['reply_parent'] = context['args'].thread
    evidence = current(binding)
    context.update(issue=issue, binding=binding, observed=evidence)
    if latest(evidence[4], 'result')[0]:
        if issue['status'] != 'in_review':
            cli('issue', 'status', binding['issue_id'], 'in_review')
        raise Completed('Already delivered to MAIN; end this turn.')


def prepare(args, context):
    """```dot
    digraph prepare {
        rankdir=LR; node [shape=box];
        prepare_check [label="Check binding and clean repository; fetch main"];
        prepare_branch [label="Reuse or create the issue feature branch"];
        prepare_status [label="Set issue in_progress"];
        prepare_check -> prepare_branch;
        prepare_branch -> prepare_status;
    }
    ```"""
    binding = context['binding']
    repo = repo_root()
    check_repo(repo, binding)
    exclude_local(repo)
    clean(repo)
    git(repo, 'fetch', 'origin', 'main')
    branch = binding['branch']
    submission = context['observed'][0]
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
    """```dot
    digraph submit {
        rankdir=LR; node [shape=box];
        submit_check [label="Require clean bound branch and one feature commit"];
        submit_test [label="Run configured test and report diff"];
        submit_push [label="Push with lease on previous submission"];
        submit_review [label="Steer Reviewer to the shared review phase"];
        submit_check -> submit_test;
        submit_test -> submit_push;
        submit_push -> submit_review;
    }
    ```"""
    binding = context['binding']
    repo = repo_root()
    check_repo(repo, binding)
    if git(repo, 'branch', '--show-current') != binding['branch']:
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
    data = {'commit': commit, 'summary': args.summary, 'answer': args.answer, 'test': evidence, 'changes': changes}
    comment(binding['issue_id'], mention(binding['reviewer_id']) +
                  ' Review this commit; approve or return corrections. ' + entry_command('multica-featssship-feature') +
                  '\n\n' + block('submission', data),
                  reply_parent(context, review_row['id'] if review_row else binding['thread_id']),
                  steer_agent=binding['reviewer_id'])
    return {'instruction': 'Review requested. End this turn; resume on Reviewer’s reply.'}


def verdict(args, context):
    """```dot
    digraph verdict {
        rankdir=LR; node [shape=box];
        verify [label="Verify clean checkout at latest submitted commit"];
        judge [label="Approve?", shape=diamond];
        check [label="Require configured check to pass"];
        publish [label="Publish answers and steer Developer"];
        verify -> judge;
        judge -> check [label="yes"];
        judge -> publish [label="return corrections"];
        check -> publish;
    }
    ```"""
    binding = context['binding']
    submission, row, _, _, _, _ = context['observed']
    repo = repo_root()
    check_repo(repo, binding)
    clean(repo)
    if not submission or git(repo, 'rev-parse', 'HEAD') != submission['commit']:
        raise ValueError('Review the exact submitted commit in the issue checkout.')
    approved = args.event == 'approve'
    data = {'commit': submission['commit'], 'submission_id': row['id'],
            'verdict': 'approved' if approved else 'rework', 'answer': args.answer,
            'necessary_additions': args.necessary_additions, 'demand_match': args.demand_match,
            'finding': args.finding}
    if approved:
        data['test'] = test(repo, binding['test_command'])
    comment(binding['issue_id'], mention(binding['developer_id']) +
            (' Integrate the approved commit.' if approved else ' Fix the findings and resubmit.') +
            ' ' + entry_command('multica-featssship-feature') + '\n\n' + block('review', data),
            reply_parent(context, row['id']), steer_agent=binding['developer_id'])
    return {'instruction': 'Verdict delivered. End this turn; Developer owns the next phase.'}


def integration(args, context):
    """```dot
    digraph integration {
        rankdir=LR; node [shape=box];
        integration_check [label="Require current independent approval and unchanged revision"];
        integration_hold [label="Manual hold released?", shape=diamond];
        integration_wait [label="Wait for human acceptance"];
        integration_merge [label="Reuse recorded integration or merge and test disposable checkout"];
        integration_rework [label="Publish correction request"];
        integration_push [label="Verify recorded integration or push and record new revision"];
        integration_source [label="Close linked source with Developer resolution when present"];
        integration_receipt [label="Send or reuse MAIN receipt; feature enters in_review"];
        integration_check -> integration_hold;
        integration_hold -> integration_wait [label="no"];
        integration_hold -> integration_merge [label="yes or absent"];
        integration_merge -> integration_rework [label="failure"];
        integration_merge -> integration_push [label="success"];
        integration_push -> integration_source;
        integration_source -> integration_receipt;
    }
    ```"""
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
    if branch == binding['branch'] and git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('The feature branch changed after approval. Submit it for fresh review.')
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
                    return {'phase': 'implement', 'instruction': 'Fix integration against current main and resubmit.'}
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
    return {'phase': 'finished'}


PARAMS = (Parameter('--answer', 'Answer to the acceptance question'),
          Parameter('--necessary-additions', 'Are the additions necessary?'),
          Parameter('--demand-match', 'Does the solution preserve the request’s scope?'),
          Parameter('--finding', 'Concrete findings or approval rationale'))

workflow = Workflow(
    State('implement', 'Developer: prepare the branch, implement or amend, then submit.', initial=True,
          precheck=observed, options=(
              Option('prepare', 'implement', 'Prepare the issue feature branch.', prepare),
              Option('submit', 'review', 'Test, push and request independent review.', submit, params=(
                  Parameter('--summary', 'Outcome, technical approach and necessary links or artifacts'),
                  Parameter('--answer', 'Optional acceptance answer', required=False),)))),
    State('review', 'Reviewer: read the issue request and acceptance questions. Inspect git diff '
          'origin/main...HEAD without editing source. Approve or return concrete corrections.',
          precheck=observed, options=(
              Option('approve', 'integrate', 'Approve the exact submitted revision after testing.', verdict, params=PARAMS),
              Option('rework', 'implement', 'Return findings to Developer.', verdict, params=PARAMS))),
    State('integrate', 'Developer: integrate the approved revision and send MAIN one verified result.',
          precheck=observed, options=(
              Option('integrate', 'integration_result', 'Merge, test, push and report.', integration),)),
    Branch('integration_result', 'Integration output', {'correction needed': 'implement', 'delivered': 'finished'}),
    State('finished', 'Delivered to MAIN; end this turn.', final=True),
    params=(Parameter('--thread', 'Native triggering comment UUID', required=False),),
)
