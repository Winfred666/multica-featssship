"""Reviewer owns one experiment; Developer answers an addressed questionnaire."""
import json
from pathlib import Path

from featssship import (DELEGATION_KEY, check_repo, clean, cli, comment, config_ref,
                       feature_config, git, link_config, mention, repo_root)
from score import evaluate
from sop import Option, Parameter, State, Workflow


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    binding = feature_config(issue)
    if issue['assignee_id'] != binding['reviewer_id'] or context['agent_id'] != binding['reviewer_id']:
        raise ValueError('Only the assigned Reviewer runs this experiment SoP. Developer answers its questionnaire.')
    context.update(issue=issue, binding=binding)


def reviewer(context):
    return {'id': context['binding']['reviewer_id'], 'name': 'Reviewer'}


def label_exp(issue_id):
    labels = cli('label', 'list')
    labels = labels.get('labels', []) if isinstance(labels, dict) else labels
    label = next((row for row in labels if row['name'] == 'exp'), None)
    label = label or cli('label', 'create', '--name', 'exp', '--color', '#8b5cf6')
    cli('issue', 'label', 'add', issue_id, label['id'])


def prepare(args, context):
    """```dot
    digraph prepare { child [label="Create/resume Developer exp child"];
        tree [label="Prepare candidate-only branch/worktree"]; child -> tree -> questionnaire; }
    ```"""
    state, binding = context['state'], context['binding']
    repo = repo_root()
    check_repo(repo, binding)
    if not state.get('developer_issue_id'):
        child = cli('issue', 'create', '--title', 'Develop: ' + context['issue']['title'],
                    '--description-stdin', '--parent', context['issue_id'],
                    '--project', context['issue']['project_id'], '--assignee-id', binding['developer_id'],
                    '--status', 'backlog', input=binding['request'])
        state['developer_issue_id'] = child['id']
        context['save_state']()
    child_id = state['developer_issue_id']
    label_exp(child_id)
    link_config(child_id, config_ref(context['issue'], DELEGATION_KEY), DELEGATION_KEY)
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    worktree = common / 'featsship' / child_id
    if not worktree.exists():
        git(repo, 'fetch', 'origin', binding['parent_branch'])
        git(repo, 'worktree', 'add', '-b', binding['branch'], str(worktree), 'FETCH_HEAD')
    if git(worktree, 'branch', '--show-current') != binding['branch']:
        raise ValueError('The candidate worktree belongs to another branch.')
    state['worktree'] = str(worktree)
    state.setdefault('base', git(worktree, 'rev-parse', 'HEAD'))
    description = (binding['request'] + '\n\nScope: ' + binding['scope'] +
                   '\n\nDevelop the candidate/idea in ' + str(worktree) +
                   '. Keep the prepared branch; commit the finished candidate. '
                   'Answer the native questionnaire here with the full candidate commit and summary when finished. '
                   'Do not run the Reviewer SoP or hidden evaluation. No integration or push-to-main.')
    cli('issue', 'update', child_id, '--description-stdin', '--no-start', input=description)
    cli('issue', 'update', child_id, '--status', 'in_progress', '--no-start')
    return {'this_round_reply_guidance': 'End this turn silently; the engine addresses the development questionnaire.'}


def developer(context):
    state, binding = context['state'], context['binding']
    return {'id': binding['developer_id'], 'issue_id': state['developer_issue_id'], 'thread': None,
            'content': mention(binding['developer_id']) + ' Develop this candidate in ' + state['worktree'] +
                       '. Answer finished only after committing, with --commit and --summary. Do not run the Reviewer SoP.'}


def submitted(args, context):
    repo = Path(context['state']['worktree'])
    clean(repo)
    if git(repo, 'branch', '--show-current') != context['binding']['branch']:
        raise ValueError('Submit from the prepared candidate branch.')
    commit = git(repo, 'rev-parse', '--verify', args.commit + '^{commit}')
    if commit != args.commit or git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Submit the full current candidate commit.')
    git(repo, 'merge-base', '--is-ancestor', context['state']['base'], commit)
    context['state'].update(commit=commit, summary=args.summary)


def score(args, context):
    """```dot
    digraph score { policy [label="Verify OS boundary and private evaluator"];
        once [label="Persist attempted before invoking canonical script once"];
        result [label="Validate finite numeric score only"]; policy -> once -> result; }
    ```"""
    evaluate(context)


def review(context):
    state, binding = context['state'], context['binding']
    return {'instruction': 'Return a concise review answering the selected questions. No re-evaluation or integration.\n' +
            json.dumps({'score': state['score']}, allow_nan=False) + '\nCandidate: ' + state['commit'] +
            '\nDeveloper summary: ' + state['summary'] + '\n' + '\n'.join(binding['questions'])}


def deliver(args, context):
    state, binding = context['state'], context['binding']
    if not state.get('delivered'):
        comment(binding['main_issue_id'], '/note\n```json\n' +
                json.dumps({'score': state['score']}, allow_nan=False) + '\n```\n' + args.review +
                '\n\nCandidate: ' + state['commit'] + '\nExperiment: ' + context['issue_id'], binding['dispatch_thread'])
        state['delivered'] = True
        context['save_state']()
    cli('issue', 'update', state['developer_issue_id'], '--status', 'in_review', '--no-start')
    cli('issue', 'update', context['issue_id'], '--status', 'in_review', '--no-start')
    return {'this_round_reply_guidance': 'End this turn silently.'}


workflow = Workflow(
    State('ready', 'Prepare one Developer experiment child.', initial=True, precheck=observed, owner=reviewer),
    Option('prepare', 'Address development to Developer.', prepare),
    State('develop', 'Develop and commit the candidate/idea, then answer finished.', precheck=observed, owner=developer),
    Option('finished', 'Candidate finished', submitted,
           params=(Parameter('--commit', 'Full candidate commit'), Parameter('--summary', 'Candidate/idea and public checks'))),
    State('evaluate', 'Run exactly one canonical private evaluation. Missing inputs/access stop here.', precheck=observed, owner=reviewer),
    Option('score', 'Run the private evaluation once.', score),
    State('review', 'Review the numeric score and direction questions.', precheck=observed, owner=reviewer,
          view=review, preview='Review {score} and selected direction questions.'),
    Option('deliver', 'Send one score JSON plus review to MAIN.', deliver, params=(Parameter('--review', 'Concise review'),)),
    State('reported', 'Result sent to MAIN; no integration or further evaluation. End this turn.', precheck=observed, owner=reviewer),
    edges=(('ready', 'prepare'), ('prepare', 'develop'), ('develop', 'finished'), ('finished', 'evaluate'),
           ('evaluate', 'score'), ('score', 'review'), ('review', 'deliver'), ('deliver', 'reported')),
)
