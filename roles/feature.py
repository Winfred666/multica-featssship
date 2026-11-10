"""Develop and review in the issue's shared folder and branch; report to MAIN."""
from pathlib import Path
import subprocess

from common import QUESTIONS, ROUND_DONE, check_repo, clean, cli, comment, entry_command, git, has_manual, mention, test, unpack
from sop import Completed, Option, Parameter, State, Workflow

REVIEW_PROMPT = ('Reviewer: inspect the submitted diff in this issue\'s shared folder and branch. '
                 'Only read and review; do not edit source, run tests, merge or push. '
                 'Answer the acceptance and review questions in --finding. Approve or return corrections.')


def require_role(context, role):
    if context['agent_id'] != context['binding'][role + '_id']:
        raise SystemExit('Rejected: this action belongs to ' + role + '.')


def review_view(context):
    # The issue owns the request and review criteria; omit only the runtime instructions/binding.
    request = context['issue']['description'].rsplit('\n\n' + entry_command('multica-featssship-develop-review'), 1)[0]
    return {'instruction': REVIEW_PROMPT + '\n\nIssue criteria (read-only reference):\n' + request}


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    binding = unpack(issue['description'], 'binding')
    if not binding:
        raise ValueError('MAIN must supply the issue’s feature configuration before development.')
    role = 'reviewer' if context['phase'] == 'review' else 'developer'
    context.update(issue=issue, binding=binding)
    if 'result' not in context:
        require_role(context, role)
    if issue['status'] in ('done', 'cancelled', 'in_review'):
        context['handoff'] = ROUND_DONE
        raise Completed(ROUND_DONE)


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
        push [label="Test, push exact revision and request Reviewer"]; check -> push; }
    ```"""
    require_role(context, 'developer')
    repo, binding = shared_repo(context), context['binding']
    git(repo, 'fetch', 'origin', 'main')
    if git(repo, 'rev-list', '--count', 'origin/main..HEAD') != '1':
        raise ValueError('Keep one feature commit; amend corrections before submitting.')
    test(repo, binding['test_command'])
    ref = 'refs/heads/' + binding['branch']
    git(repo, 'push', '--force-with-lease=' + ref + ':' + context['state'].get('commit', ''), 'origin', 'HEAD:' + ref)
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
    require_role(context, 'reviewer')
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    commit = state['commit']
    if git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Review the exact submitted revision; changed code needs a new submission.')
    approved = args.event == 'approve'
    if approved:
        state['finding'] = args.finding
    comment(context['issue_id'], mention(binding['developer_id']) + ' TODO: ' +
            ('Integrate approved ' if approved else 'Correct ') +
            '[result](mention://issue/' + context['issue_id'] + ') at ' + commit + '.\n' +
            args.finding + '\n\n' + entry_command('multica-featssship-develop-review'),
            getattr(args, 'thread', None), steer_agent=binding['developer_id'])
    context['handoff'] = ROUND_DONE


def integrate(args, context):
    """```dot
    digraph integrate { node [shape=box]; check [label="Developer: check approved HEAD"];
        manual [shape=diamond, label="Manual check?"]; merge [label="Test, merge main and test"];
        report [label="Push main or report manual handling to MAIN"];
        check -> manual; manual -> report [label="yes"]; manual -> merge [label="no"]; merge -> report; }
    ```"""
    require_role(context, 'developer')
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    commit = state['commit']
    if git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Integrate the exact approved revision; changed code needs a new review.')
    note = 'Manual check required for ' + commit + ': ' + state['finding']
    if not has_manual(context['issue']):
        try:
            test(repo, binding['test_command'])
            if git(repo, 'ls-remote', 'origin', 'refs/heads/' + binding['branch']).split()[0] != commit:
                raise ValueError('The remote feature branch changed after submission.')
            git(repo, 'fetch', 'origin', 'main')
            git(repo, 'merge', '--no-edit', 'origin/main')
            test(repo, binding['test_command'])
            git(repo, 'push', 'origin', 'HEAD:refs/heads/main')
            note = 'Merged ' + git(repo, 'rev-parse', 'HEAD') + ': ' + state['summary'] + '\nReview: ' + state['finding']
        except ValueError as error:
            subprocess.run(['git', 'merge', '--abort'], cwd=repo, capture_output=True)
            note = 'Manual check required for ' + commit + ': ' + str(error)
    parent = context['issue']['parent_issue_id']
    main = cli('issue', 'get', parent)
    comment(parent, mention(main['assignee_id']) +
            ' TODO: Review the [Feature](mention://issue/' + context['issue_id'] + ') result.\n\n' + note,
            steer_agent=main['assignee_id'])
    cli('issue', 'status', context['issue_id'], 'in_review')
    context['handoff'] = ROUND_DONE
    return {'instruction': note + '\nReported to MAIN; end this turn.'}


workflow = Workflow(
    State('develop', 'Developer: implement the issue request on MAIN’s feature branch in the current issue folder. '
          'Keep one feature commit; amend corrections. Test and submit.', initial=True, precheck=observed,
          options=(Option('submit', 'review', 'Test, push and request independent review.', submit,
                          params=(Parameter('--summary', 'Delivered behavior and evidence'),)),)),
    State('review', REVIEW_PROMPT + '\n\nDefault review questions:\n' + '\n'.join('- ' + q for q in QUESTIONS) +
          '\n\nAlso answer the feature-specific Acceptance question from this issue.',
          precheck=observed, view=review_view, options=(
              Option('approve', 'integrate', 'Approve the revision and return integration to Developer.', verdict,
                     params=(Parameter('--finding', 'Acceptance answer and review evidence'),)),
              Option('rework', 'develop', 'Send corrections to Developer.', verdict,
                     params=(Parameter('--finding', 'Concrete corrections'),)))),
    State('integrate', 'Developer: integrate the approved revision, run the configured tests and report '
          'one verified result to MAIN.', precheck=observed,
          options=(Option('integrate', 'finished', 'Integrate and test, or report manual handling to MAIN.', integrate),)),
    State('finished', 'Reported to MAIN; end this turn.', final=True),
    params=(Parameter('--thread', 'Native triggering comment UUID', required=False),),
)
