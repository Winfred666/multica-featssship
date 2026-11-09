"""Question-specific independent Reviewer. Source changes belong to Developer."""
import json
from pathlib import Path

from common import (block, check_repo, clean, comment, current, entry_command, feature,
                    git, mention, reply_parent, repo_root, test)
from sop import Option, Parameter, State, Workflow

ROOT = Path(__file__).resolve().parent


def observed(context):
    issue, binding = feature(context, 'reviewer')
    if context['args'].thread:
        context['state']['reply_parent'] = context['args'].thread
    compiled = json.loads((ROOT / 'review.json').read_text())
    submission, row, review, review_row, _, _ = current(binding)
    if not submission or compiled.get('commit') != submission['commit']:
        raise ValueError('Use the current compiled Reviewer package for the latest submitted revision.')
    if compiled['issue_id'] != binding['issue_id'] or compiled['question'] != binding['question']:
        raise ValueError('The compiled question does not match the feature binding.')
    context.update(binding=binding, submission=submission, submission_row=row, review=review, review_row=review_row)
    return {'request': binding['request'], 'scope': binding['scope'], 'question': compiled['question'],
            'questions': compiled['questions'], 'submission': submission}


def view(context):
    return {'data': context['initial']}


def prepare(args, context):
    repo = repo_root()
    check_repo(repo, context['binding'])
    clean(repo)
    git(repo, 'fetch', 'origin', '+refs/heads/main:refs/remotes/origin/main', context['binding']['branch'])
    commit = context['submission']['commit']
    checkout = repo / '.multica' / 'featssship' / ('review-' + context['task_id'])
    from common import exclude_local
    exclude_local(repo)
    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        git(repo, 'worktree', 'add', '--detach', str(checkout), commit)
    if git(checkout, 'rev-parse', 'HEAD') != commit:
        raise ValueError('The review checkout does not match the submitted revision.')
    evidence = test(checkout, context['binding']['test_command'], required=False)
    context['state']['test_evidence'] = evidence
    return {'data': {'checkout': str(checkout), 'commit': commit, 'test': evidence,
                     'diff_command': f'git -C {checkout} diff origin/main...{commit}'},
            'instruction': 'Inspect the request, source and diff. Answer the review questions; approve or return corrections.'}


def verdict(args, context):
    binding = context['binding']
    commit = context['submission']['commit']
    checkout = repo_root() / '.multica' / 'featssship' / ('review-' + context['task_id'])
    if not checkout.exists() or git(checkout, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Prepare and inspect this task’s submitted checkout first.')
    clean(checkout)
    if context['review']:
        return {'data': {'review_id': context['review_row']['id']}, 'instruction': 'Verdict already delivered; end this turn.'}
    data = {'commit': commit, 'submission_id': context['submission_row']['id'],
            'verdict': 'approved' if args.event == 'approve' else 'rework',
            'answer': args.answer, 'necessary_additions': args.necessary_additions,
            'demand_match': args.demand_match, 'finding': args.finding}
    if args.event == 'approve':
        data['test'] = context['state']['test_evidence']
        if data['test']['exit_code']:
            raise ValueError('The submitted revision failed its configured check. Return corrections.')
    row = comment(binding['issue_id'], mention(binding['developer_id']) +
                  (' Integrate the approved commit.' if args.event == 'approve' else ' Fix the findings and resubmit.') +
                  ' ' + entry_command('multica-featssship-developer') + '\n\n' + block('review', data),
                  reply_parent(context, context['submission_row']['id']), steer_agent=binding['developer_id'])
    git(repo_root(), 'worktree', 'remove', str(checkout))
    return {'data': {'review_id': row['id'], **data}}


PARAMS = (Parameter('--answer', 'Answer to the requested acceptance question'),
          Parameter('--necessary-additions', 'Are the additions necessary?'),
          Parameter('--demand-match', 'Does the solution preserve the request’s scope?'),
          Parameter('--finding', 'Concrete findings or approval rationale'))

workflow = Workflow(
    State('receive', 'Read the request and submitted commit.', initial=True, precheck=observed, view=view, options=(
        Option('prepare', 'inspect', 'Fetch and test the exact submitted revision in a disposable checkout.', prepare),)),
    State('inspect', 'Inspect the diff and answer the review questions.', precheck=observed, view=view, options=(
        Option('approve', 'finished', 'Approve this submitted commit.', verdict, params=PARAMS),
        Option('rework', 'finished', 'Return concrete corrections to Developer.', verdict, params=PARAMS),)),
    State('finished', 'Verdict delivered; end this turn.', final=True),
    params=(Parameter('--thread', 'Native triggering comment UUID for this task', required=False),),
)
