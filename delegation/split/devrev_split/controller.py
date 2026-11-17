"""Reviewer owns one experiment; Developer answers an addressed questionnaire."""
import json
from pathlib import Path

from featssship import (DELEGATION_KEY, check_repo, clean, cli, comment, config_ref,
                       feature_config, git, link_config, mention, repo_root, run, wake_agent)
from score import evaluate, numeric_score
from sop import Completed, Option, Parameter, State, Workflow

SUBMITTED_KEY = 'featssship.experiment_submitted'
DEVELOPER_REPLY_GUIDANCE = (
    'At the start of development, attach a visual image of this variant\'s connected module pipeline '
    'to the Developer issue. Update that image as the pipeline changes (reuse its attachment ID). '
    'Prefer an ontology module dictionary and a detailed local pipeline using the project\'s existing format. '
    'Keep the pipeline file in the candidate commit. When finished, answer candidate_ready with '
    '--commit, --summary, --pipeline and --visual-attachment. Do not run the Reviewer SoP or hidden evaluation.')


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    binding = feature_config(issue)
    if issue['assignee_id'] != binding['reviewer_id'] or context['agent_id'] != binding['reviewer_id']:
        raise ValueError('Only the assigned Reviewer runs this experiment SoP. Developer answers its questionnaire.')
    context.update(issue=issue, binding=binding)
    if issue['metadata'].get(SUBMITTED_KEY) or issue['status'] in ('in_review', 'done', 'cancelled'):
        raise Completed('Experiment already submitted or closed. End this turn silently.', target=Workflow.FINISHED)
    if context['args'].thread:
        context['state']['review_thread'] = context['args'].thread
    elif context['native_issue_id'] == context['issue_id'] and context['native_comment_id']:
        context['state'].setdefault('review_thread', context['native_comment_id'])


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
    if not state.get('review_thread'):
        raise ValueError('Start the Reviewer SoP with --thread from the experiment issue description.')
    context['args'].thread = state['review_thread']
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
    if not state.get('developer_thread'):
        state['developer_thread'] = comment(child_id, '/note Development questionnaire thread.')['id']
        context['save_state']()
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
    description = (binding['request'] + '\n\nScope: ' + binding['scope'] + '\n\nVariant: ' + binding['name'] +
                   '\n\nDevelop the candidate/idea in ' + str(worktree) +
                   '. Keep the prepared branch; commit the finished candidate. '
                   'No integration or push-to-main.\n\n' + DEVELOPER_REPLY_GUIDANCE)
    cli('issue', 'update', child_id, '--description-stdin', '--no-start', input=description)
    cli('issue', 'update', child_id, '--status', 'in_progress', '--no-start')
    return {'this_round_reply_guidance':
            'End this turn silently. The native questionnaire forwards this Developer reply guidance:\n' +
            DEVELOPER_REPLY_GUIDANCE}


def developer(context):
    state, binding = context['state'], context['binding']
    return {'id': binding['developer_id'], 'issue_id': state['developer_issue_id'], 'thread': state['developer_thread'],
            'content': mention(binding['developer_id']) + ' Develop variant ' + binding['name'] + ' in ' +
                       state['worktree'] + '.\n\n' + DEVELOPER_REPLY_GUIDANCE}


def submitted(args, context):
    repo = Path(context['state']['worktree'])
    clean(repo)
    if git(repo, 'branch', '--show-current') != context['binding']['branch']:
        raise ValueError('Submit from the prepared candidate branch.')
    commit = git(repo, 'rev-parse', '--verify', args.commit + '^{commit}')
    if commit != args.commit or git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Submit the full current candidate commit.')
    git(repo, 'merge-base', '--is-ancestor', context['state']['base'], commit)
    if not git(repo, 'diff', '--name-only', context['state']['base'], commit, '--'):
        raise ValueError('Complete and commit a candidate with actual changes before answering.')
    if git(repo, 'cat-file', '-t', commit + ':' + args.pipeline) != 'blob':
        raise ValueError('--pipeline must name a committed local pipeline file.')
    image = json.loads(run('multica', 'attachment', 'get', args.visual_attachment))
    if not image.get('content_type', '').startswith('image/'):
        raise ValueError('--visual-attachment must reference a visual image, not HTML or a text file.')
    developer = cli('issue', 'get', context['state']['developer_issue_id'])
    linked = developer.get('metadata', {}).get('independent_artifacts', '[]')
    linked = json.loads(linked) if isinstance(linked, str) else linked
    if image.get('issue_id') != developer['id'] and image['id'] not in linked:
        raise ValueError('Attach the pipeline image to the Developer issue before answering.')
    context['state'].update(commit=commit, summary=args.summary, pipeline=args.pipeline,
                            visual={'id': image['id'], 'url': image['markdown_url']})
    context['save_state']()
    wake_agent({**context, 'native_comment_id': context['state']['review_thread']}, context['binding']['reviewer_id'], 'Candidate ready: variant ' +
               context['binding']['name'] + '. Inspect its local pipeline and visual, then submit the experiment.')
    return {'this_round_reply_guidance': 'End this turn silently; Reviewer has been notified.'}


def review(context):
    state, binding = context['state'], context['binding']
    pipeline = git(Path(state['worktree']), 'show', state['commit'] + ':' + state['pipeline'])
    return {'instruction': 'Inspect the variant, detailed local pipeline and visual without editing source. '
            'Answer the direction questions in --review. submit runs one canonical evaluation, validates score JSON, '
            'posts score plus review directly to MAIN and enters finished.\nVariant: ' + binding['name'] +
            '\nCandidate: ' + state['commit'] + '\nDeveloper summary: ' + state['summary'] +
            '\nPipeline: ' + state['pipeline'] + '\n' + pipeline +
            '\nVisual: ' + state['visual']['url'] + '\n' + '\n'.join(binding['questions'])}


def submit(args, context):
    """```dot
    digraph submit { policy [label="Check private evaluator boundary"];
        once [label="Run once and validate finite numeric score"];
        main [label="Post score, variant, pipeline and review directly to MAIN"];
        policy -> once -> main -> finished; }
    ```"""
    state, binding = context['state'], context['binding']
    # Publication retries reuse the saved real score, never another evaluation.
    if 'score' not in state:
        evaluate(context)
    score_json = json.dumps({'score': state['score']}, allow_nan=False)
    numeric_score(score_json)
    if not state.get('delivered'):
        comment(binding['main_issue_id'], '/note\n```json\n' +
                score_json + '\n```\n' + args.review +
                '\n\nVariant: ' + binding['name'] + '\nPipeline: ' + str(Path(state['worktree']) / state['pipeline']) +
                '\n![Variant pipeline](' + state['visual']['url'] + ')' +
                '\nCandidate: ' + state['commit'] + '\nExperiment: ' + context['issue_id'], binding['dispatch_thread'])
        state['delivered'] = True
        context['save_state']()
    cli('issue', 'update', state['developer_issue_id'], '--status', 'in_review', '--no-start')
    cli('issue', 'update', context['issue_id'], '--status', 'in_review', '--no-start')
    cli('issue', 'metadata', 'set', context['issue_id'], '--key', SUBMITTED_KEY, '--value', 'true', '--type', 'string')
    return {'this_round_reply_guidance': 'End this turn silently.'}


workflow = Workflow(
    State('ready', 'Prepare one Developer experiment child.', initial=True, precheck=observed, owner=reviewer),
    Option('prepare', 'Address development to Developer.', prepare),
    State('develop', DEVELOPER_REPLY_GUIDANCE, precheck=observed, owner=developer),
    Option('candidate_ready', 'Candidate, pipeline and visual ready', submitted,
           params=(Parameter('--commit', 'Full candidate commit'), Parameter('--summary', 'Candidate/idea and public checks'),
                   Parameter('--pipeline', 'Committed local pipeline file'), Parameter('--visual-attachment', 'Visual image attachment ID'))),
    State('review', 'Inspect the variant and submit one evaluation plus review.', precheck=observed, owner=reviewer,
          view=review, preview='Review {variant}, {pipeline}, image and direction questions before submit.'),
    Option('submit', 'Evaluate once and send score JSON plus required review directly to MAIN.', submit,
           params=(Parameter('--review', 'Concise variant review answering the direction questions'),)),
    State('finished', 'Score and review sent to MAIN. End this turn silently.', final=True),
    edges=(('ready', 'prepare'), ('prepare', 'develop'), ('develop', 'candidate_ready'), ('candidate_ready', 'review'),
           ('review', 'submit'), ('submit', 'finished')),
    params=(Parameter('--thread', 'Reviewer experiment thread from its issue description', required=False),),
)
