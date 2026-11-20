"""Dispatch a Reviewer-owned experiment child."""
from pathlib import Path
from featssship import DELEGATION_KEY, cli, comment, git, link_config
from batch import save_progress


def exp_label(issue_id):
    labels = cli('label', 'list')
    labels = labels.get('labels', []) if isinstance(labels, dict) else labels
    label = next((row for row in labels if row['name'] == 'exp'), None)
    label = label or cli('label', 'create', '--name', 'exp', '--color', '#8b5cf6')
    cli('issue', 'label', 'add', issue_id, label['id'])


def dispatch_experiment(context, request, item, index):
    if item.get('dispatched'):
        return
    if not item.get('issue_id'):
        child = cli('issue', 'create', '--title', request.get('title') or request['name'],
                    '--description-stdin', '--parent', context['issue_id'],
                    '--project', context['main']['project_id'],
                    '--assignee-id', context['installed']['installed_reviewer_id'],
                    '--status', 'backlog', input=request['request'])
        item['issue_id'] = child['id']
        save_progress(context)
    exp_label(item['issue_id'])
    link_config(item['issue_id'], {**context['reference'], 'index': index}, DELEGATION_KEY)
    if not item.get('review_thread'):
        item['review_thread'] = comment(item['issue_id'], '/note Experiment review thread.')['id']
        save_progress(context)
    description = (request['request'] + '\n\nScope: ' + request['scope'] + '\n\nVariant: ' + request['name'] +
                   '\n\nReviewer owns this experiment. From ' + str(Path(git(Path(__file__).resolve().parent, 'rev-parse', '--show-toplevel')).resolve()) +
                   ', run `multica sop run multica-featssship-devrev-split --thread ' + item['review_thread'] + '`. '
                   'No integration or push-to-main. Hidden inputs stay outside shared settings.\n\n' +
                   Path(__file__).with_name('PROJECT.md').read_text().strip())
    cli('issue', 'update', item['issue_id'], '--description-stdin', '--no-start', input=description)
    if cli('issue', 'get', item['issue_id'])['status'] == 'backlog':
        cli('issue', 'status', item['issue_id'], 'todo')
    item['dispatched'] = True
    save_progress(context)
