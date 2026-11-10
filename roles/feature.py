"""Develop and review in the issue's shared folder and branch; report to MAIN."""
from pathlib import Path
import subprocess

from common import QUESTIONS, clean, cli, comment, entry_command, git, has_manual, mention, test, unpack
from sop import Completed, Option, Parameter, State, Workflow

REVIEW_PROMPT = ('Reviewer: inspect the submitted diff in this issue\'s shared folder and branch. '
                 'Do not create a checkout, switch branches or edit source. Answer the acceptance and '
                 'review questions in --finding. Approve to merge or return concrete corrections. '
                 'Developer: end this turn after submitting.')


def review_view(context):
    # The issue owns the request and review criteria; omit only the runtime instructions/binding.
    request = context['issue']['description'].rsplit('\n\n' + entry_command('multica-featssship-develop-review'), 1)[0]
    return {'instruction': REVIEW_PROMPT + '\n\n' + request}


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    binding = unpack(issue['description'], 'binding')
    if not binding:
        raise ValueError('MAIN must supply the issue’s feature configuration before development.')
    role = 'reviewer' if context['phase'] == 'review' else 'developer'
    if 'result' not in context and context['agent_id'] != binding[role + '_id']:
        context['state'] = {}
        raise context['error']('wrong_agent', 'This phase belongs to ' + role + '.')
    if issue['status'] in ('done', 'cancelled', 'in_review'):
        raise Completed('Already reported to MAIN; end this turn.')
    context.update(issue=issue, binding=binding)


def shared_repo(context):
    repo = Path.cwd()
    clean(repo)
    if git(repo, 'branch', '--show-current') != context['binding']['branch']:
        raise ValueError('Use the feature branch supplied by MAIN in this issue folder.')
    return repo


def submit(args, context):
    """```dot
    digraph submit { node [shape=box]; check [label="Test clean feature commit"];
        push [label="Push branch and request Reviewer"]; check -> push; }
    ```"""
    repo, binding = shared_repo(context), context['binding']
    git(repo, 'fetch', 'origin', 'main')
    if git(repo, 'rev-list', '--count', 'origin/main..HEAD') != '1':
        raise ValueError('Keep one feature commit; amend corrections before submitting.')
    test(repo, binding['test_command'])
    git(repo, 'push', '--force-with-lease', 'origin', 'HEAD:refs/heads/' + binding['branch'])
    context['state'].update(commit=git(repo, 'rev-parse', 'HEAD'), summary=args.summary)
    comment(context['issue_id'], mention(binding['reviewer_id']) + ' Review ' + context['state']['commit'] +
            ': ' + args.summary + '\n\n' + entry_command('multica-featssship-develop-review'),
            getattr(args, 'thread', None), steer_agent=binding['reviewer_id'])


def verdict(args, context):
    """```dot
    digraph verdict { node [shape=box]; inspect [label="Check shared tree and submitted HEAD"];
        rework [label="Return findings to Developer"]; manual [shape=diamond, label="Manual check?"];
        merge [label="Merge main and test"];
        report [label="Push main or send MAIN a manual-check note"];
        inspect -> rework [label="rework"]; inspect -> manual [label="approve"];
        manual -> report [label="yes"]; manual -> merge [label="no"]; merge -> report; }
    ```"""
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    commit = state['commit']
    if git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Review the exact submitted revision; changed code needs a new submission.')
    if args.event == 'rework':
        comment(context['issue_id'], mention(binding['developer_id']) + ' ' + args.finding +
                '\n\n' + entry_command('multica-featssship-develop-review'),
                getattr(args, 'thread', None), steer_agent=binding['developer_id'])
        return {'instruction': 'Developer: correct the findings, amend and submit. Reviewer: end this turn.'}
    note = 'Manual check required for ' + commit + ': ' + args.finding
    if not has_manual(context['issue']):
        try:
            test(repo, binding['test_command'])
            if git(repo, 'ls-remote', 'origin', 'refs/heads/' + binding['branch']).split()[0] != commit:
                raise ValueError('The remote feature branch changed after submission.')
            git(repo, 'fetch', 'origin', 'main')
            git(repo, 'merge', '--no-edit', 'origin/main')
            test(repo, binding['test_command'])
            git(repo, 'push', 'origin', 'HEAD:refs/heads/main')
            note = 'Merged ' + git(repo, 'rev-parse', 'HEAD') + ': ' + state['summary'] + '\nReview: ' + args.finding
        except ValueError as error:
            subprocess.run(['git', 'merge', '--abort'], cwd=repo, capture_output=True)
            note = 'Manual check required for ' + commit + ': ' + str(error)
    parent = context['issue']['parent_issue_id']
    main = cli('issue', 'get', parent)
    comment(parent, mention(main['assignee_id']) + ' [Feature](mention://issue/' + context['issue_id'] + ')\n\n' + note,
            steer_agent=main['assignee_id'])
    cli('issue', 'status', context['issue_id'], 'in_review')
    return {'instruction': note + '\nReported to MAIN; end this turn.'}


workflow = Workflow(
    State('develop', 'Developer: implement the issue request in the supplied branch and current folder. '
          'Keep one feature commit; amend corrections. Test and submit.', initial=True, precheck=observed,
          options=(Option('submit', 'review', 'Test, push and request independent review.', submit,
                          params=(Parameter('--summary', 'Delivered behavior and evidence'),)),)),
    State('review', REVIEW_PROMPT + '\n\nDefault review questions:\n' + '\n'.join('- ' + q for q in QUESTIONS) +
          '\n\nAlso answer the feature-specific Acceptance question from this issue.',
          precheck=observed, view=review_view, options=(
              Option('approve', 'finished', 'Merge and test, or report manual handling to MAIN.', verdict,
                     params=(Parameter('--finding', 'Acceptance answer and review evidence'),)),
              Option('rework', 'develop', 'Send corrections to Developer.', verdict,
                     params=(Parameter('--finding', 'Concrete corrections'),)))),
    State('finished', 'Reported to MAIN; end this turn.', final=True),
    params=(Parameter('--thread', 'Native triggering comment UUID', required=False),),
)
