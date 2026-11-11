"""Develop and review in the issue's shared folder and branch; report to MAIN."""
from pathlib import Path
import os

from common import ROUND_DONE, REWORK_DONE, check_repo, clean, cli, comment, entry_command, feature_config, git, has_manual, mention, run, test
from sop import Branch, Completed, Option, Parameter, State, Workflow

REVIEW_PROMPT = ('Reviewer: inspect the submitted diff in this issue\'s shared folder and branch. '
                 'Only read and review; do not edit source, run tests, merge or push. '
                 'Answer the acceptance and review questions in --finding. Approve or return corrections.')

# TODO: break agent-as-middle-layer: the runtime should stop until superior input directly.
MANUAL_WAIT = 'Auto review pass, directly and silently exit until superior instruction, if outer confirmation has not been received yet.'


def require_role(context, role):
    if context['agent_id'] != context['binding'][role + '_id']:
        raise SystemExit('Rejected: this action belongs to ' + role + '.')


def review_view(context):
    # The issue owns the request and review criteria; omit only the runtime instructions/binding.
    request = context['issue']['description'].rsplit('\n\n' + entry_command('multica-featssship-develop-review'), 1)[0]
    return {'instruction': REVIEW_PROMPT + '\n\nIssue criteria (read-only reference):\n' + request +
            '\n\nReview questions:\n' + '\n'.join('- ' + q for q in context['binding']['questions'])}


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    binding = feature_config(issue)
    role = 'reviewer' if context['phase'] == 'review' else 'developer'
    context.update(issue=issue, binding=binding)
    if 'result' not in context:
        require_role(context, role)
    if issue['status'] in ('done', 'in_review') or (issue['status'] == 'cancelled' and not context['state'].get('cancel_reason')):
        context['handoff'] = ROUND_DONE
        raise Completed(ROUND_DONE, target='reported')


def shared_repo(context):
    repo = Path.cwd()
    clean(repo)
    check_repo(repo, context['binding'])
    branch = git(repo, 'branch', '--show-current')
    if branch != context['binding']['branch']:
        raise ValueError('Use the one feature branch selected by MAIN in this issue folder.')
    return repo


def submit(args, context):
    """```dot
    digraph submit { node [shape=box]; check [label="Verify repository, MAIN branch and one feature commit"];
        push [label="Test; push only if manual; request Reviewer"]; check -> push; }
    ```"""
    require_role(context, 'developer')
    repo, binding = shared_repo(context), context['binding']
    git(repo, 'fetch', 'origin', binding['parent_branch'])
    if git(repo, 'rev-list', '--count', '--no-merges', 'origin/' + binding['parent_branch'] + '..HEAD') != '1':
        raise ValueError('Keep one non-merge feature commit; amend corrections. Conflict-resolution merge commits are allowed.')
    test(repo, binding['test_command'])
    ref = 'refs/heads/' + binding['branch']
    if binding.get('manual', has_manual(context['issue'])):
        git(repo, 'push', '--force-with-lease=' + ref + ':' + context['state'].get('commit', context['issue']['metadata'].get('git_base_commit', '')), 'origin', 'HEAD:' + ref)
    context['state'].update(commit=git(repo, 'rev-parse', 'HEAD'), summary=args.summary)
    comment(context['issue_id'], mention(binding['reviewer_id']) +
            ' TODO: Review [result](mention://issue/' + context['issue_id'] + ') at ' + context['state']['commit'] +
            ': ' + args.summary + '\n\n' + entry_command('multica-featssship-develop-review'),
            getattr(args, 'thread', None), steer_agent=binding['reviewer_id'])
    context['handoff'] = ROUND_DONE


def verdict(args, context):
    """```dot
    digraph verdict { node [shape=box]; inspect [label="Read submitted revision"];
        rework [label="Return corrections to Developer"];
        approve [label="Approve; Developer owns integration"];
        inspect -> rework [label="rework"]; inspect -> approve [label="approve"]; }
    ```"""
    require_role(context, 'reviewer' if context['phase'] == 'review' else 'developer')
    if context['phase'] == 'manual_approve':
        rows = cli('issue', 'comment', 'list', context['issue_id'], '--thread', args.thread or context['state']['manual_comment_id'], '--tail', '30')
        gate = next(row for row in rows if row['id'] == context['state']['manual_comment_id'])
        main = cli('issue', 'get', context['issue']['parent_issue_id'])
        outer = next((row for row in reversed(rows) if row['id'] == args.thread or
                      (not args.thread and (row.get('author_type') == 'member' or row.get('author_id') == main['assignee_id']))), None)
        if (not outer or rows.index(outer) <= rows.index(gate)
                or not (outer.get('author_type') == 'member' or outer.get('author_id') == main['assignee_id'])
                or outer['content'].strip().split(maxsplit=1)[0].rstrip(':').casefold() != args.event):
            raise ValueError('ONLY outer allowed: reply approve, rework or cancel after the automated review, then pass that comment with --thread.')
    if args.event == 'cancel':
        context['state']['cancel_reason'] = args.reason
        cli('issue', 'status', context['issue_id'], 'cancelled')
        return {'phase': 'finished'}
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    commit = state['commit']
    if git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Review the exact submitted revision; changed code needs a new submission.')
    approved = args.event == 'approve'
    if approved:
        state['finding'] = (state['finding'] + '\nOuter approval: ' + args.finding
                            if context['phase'] == 'manual_approve' else args.finding)
        if context['phase'] == 'review' and binding.get('manual', has_manual(context['issue'])):
            row = comment(context['issue_id'], MANUAL_WAIT + '\n\nONLY outer allowed: reply approve, rework or cancel.', args.thread)
            state['manual_comment_id'] = row['id']
            context['handoff'] = MANUAL_WAIT
            return {'phase': 'manual_approve'}
    if context['phase'] == 'manual_approve':
        return {'phase': 'finished' if approved else 'develop'}
    comment(context['issue_id'], mention(binding['developer_id']) + ' TODO: ' +
            ('Finish approved ' if approved else 'Correct ') +
            '[result](mention://issue/' + context['issue_id'] + ') at ' + commit + '.\n' +
            args.finding + '\n\n' + entry_command('multica-featssship-develop-review'),
            getattr(args, 'thread', None), steer_agent=binding['developer_id'])
    context['handoff'] = ROUND_DONE if approved else REWORK_DONE
    return {'phase': 'finished' if approved else 'develop'}


def finish(args, context):
    """```dot
    digraph finish { node [shape=box]; check [label="Developer: verify owned worktree"];
        cancelled [shape=diamond, label="Cancelled?"];
        merge [label="Verify approved HEAD; test, merge parent and test"];
        conflict [shape=diamond, label="Merge conflict?"];
        rework [label="Resolve conflict, commit merge; return to develop"];
        cleanup [label="Delete local worktree and branch"];
        push [label="Push integrated commit to remote parent"];
        report [label="Report result to MAIN"];
        check -> cancelled; cancelled -> cleanup [label="yes"];
        cancelled -> merge [label="no"]; merge -> conflict;
        conflict -> rework [label="yes"]; conflict -> cleanup [label="no"];
        cleanup -> push [label="approved"]; cleanup -> report [label="cancelled"]; push -> report; }
    ```"""
    require_role(context, 'developer')
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    if repo.resolve() != (common / 'featsship' / context['issue_id']).resolve():
        raise ValueError('Finish from this issue’s prepared feature worktree.')
    cleanup = bool(state.get('cancel_reason'))
    if cleanup:
        note = 'Cancelled: ' + state['cancel_reason']
    else:
        commit = state['commit']
        if git(repo, 'rev-parse', 'HEAD') != commit:
            raise ValueError('Finish the exact approved revision; changed code needs a new review.')
        try:
            test(repo, binding['test_command'])
            if binding.get('manual', has_manual(context['issue'])) and git(repo, 'ls-remote', 'origin', 'refs/heads/' + binding['branch']).split()[0] != commit:
                raise ValueError('The remote feature branch changed after submission.')
            git(repo, 'fetch', 'origin', binding['parent_branch'])
            git(repo, 'merge', '--no-edit', 'origin/' + binding['parent_branch'])
            test(repo, binding['test_command'])
            integrated = git(repo, 'rev-parse', 'HEAD')
            note = 'Merged ' + integrated + ': ' + state['summary'] + '\nReview: ' + state['finding']
            cleanup = True
        except ValueError as error:
            if git(repo, 'ls-files', '--unmerged'):
                return {'phase': 'develop', 'instruction': 'Merge conflict: resolve it in this worktree, commit the resolution as a merge commit, then submit for review again.'}
            note = 'Manual check required for ' + commit + ': ' + str(error)
    if cleanup:
        os.chdir(common)
        run('git', '--git-dir', str(common), 'worktree', 'remove', str(repo))
        run('git', '--git-dir', str(common), 'branch', '-D', binding['branch'])
        note += '\nRemoved the local feature worktree and branch.'
        if not state.get('cancel_reason'):
            try:
                run('git', '--git-dir', str(common), 'push', 'origin', integrated + ':refs/heads/' + binding['parent_branch'])
            except ValueError as error:
                run('git', '--git-dir', str(common), 'branch', binding['branch'], integrated)
                run('git', '--git-dir', str(common), 'worktree', 'add', str(repo), binding['branch'])
                return {'phase': 'develop', 'instruction': 'Parent push failed; restored the local branch/worktree for rework. Merge the latest parent, commit the resolution and submit again. ' + str(error)}
    parent = context['issue']['parent_issue_id']
    main = cli('issue', 'get', parent)
    comment(parent, mention(main['assignee_id']) +
            ' TODO: Review the [Feature](mention://issue/' + context['issue_id'] + ') result.\n\n' + note,
            steer_agent=main['assignee_id'])
    if not state.get('cancel_reason'):
        cli('issue', 'status', context['issue_id'], 'in_review')
    context['handoff'] = ROUND_DONE
    return {'phase': 'reported', 'instruction': note + '\nReported to MAIN; end this turn.'}


workflow = Workflow(
    State('develop', 'Developer: implement the issue request on MAIN’s feature branch in the current issue folder. '
          'Keep one non-merge feature commit; amend corrections. Conflict-resolution merge commits are allowed. Test and submit.', initial=True, precheck=observed,
          options=(Option('submit', 'review', 'Test and request independent review; push only if manual.', submit,
                          params=(Parameter('--summary', 'Delivered behavior and evidence'),)),
                   Option('cancel', 'finished', 'Cancel for wrong feature scope, incomplete Git/version infrastructure, or refactoring beyond the allowed edit budget; preserve or commit edits first.', verdict,
                          params=(Parameter('--reason', 'Concrete blocker preventing this feature'),)),)),
    State('review', REVIEW_PROMPT + '\n\nAnswer this issue’s selected questions from process metadata.',
          precheck=observed, view=review_view, options=(
              Option('approve', 'approval', 'Approve the revision; manual config waits for outer approval.', verdict,
                     params=(Parameter('--finding', 'Acceptance answer and review evidence'),)),
              Option('rework', 'develop', 'Send corrections to Developer.', verdict,
                     params=(Parameter('--finding', 'Concrete corrections'),)))),
    Branch('approval', 'manual config?', {'manual': 'manual_approve', 'automatic': 'finished'}),
    State('manual_approve', MANUAL_WAIT, precheck=observed, options=(
        Option('rework', 'develop', 'ONLY outer allowed: send the requested corrections to Developer.', verdict,
               params=(Parameter('--finding', 'Superior-requested corrections'),)),
        Option('approve', 'finished', 'ONLY outer allowed: approve final integration and cleanup.', verdict,
               params=(Parameter('--finding', 'Superior approval evidence'),)),
        Option('cancel', 'finished', 'ONLY outer allowed: cancel the feature and clean up without integration.', verdict,
               params=(Parameter('--reason', 'Superior cancellation reason'),)),
    )),
    State('finished', 'Developer: for approval, integrate, delete the local feature branch/worktree, then push the approved commit to the remote parent. For cancellation, only delete locally. Report to MAIN.',
          precheck=observed, options=(Option('finish', 'completion', 'Finish approved integration or cancellation; delete locally before pushing the approved result.', finish),)),
    Branch('completion', 'Integration outcome?', {'rework: merge conflict or rejected push': 'develop', 'finished/cancelled': 'reported'}),
    State('reported', 'Reported to MAIN; end this turn.', final=True),
    params=(Parameter('--thread', 'Native triggering comment UUID', required=False),),
)
