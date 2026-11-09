"""Optional existing GitHub source issue and its verified resolution."""
import json
import re
import tempfile

from common import run


def issue_link(title, explicit=None):
    mirror = re.fullmatch(r'\[(.+)\]\((https://github\.com/[^\s)]+)\)', title)
    url = explicit or (mirror[2] if mirror else None)
    if url and not re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+/issues/[1-9][0-9]*', url):
        raise ValueError('Supply an existing GitHub issue URL: https://github.com/OWNER/REPO/issues/NUMBER')
    if explicit and mirror and mirror[2] != explicit:
        raise ValueError('The title and --github-issue must identify the same source issue.')
    return url


def mirror_title(title, url):
    return title if issue_link(title) else f'[{title}]({url})'


def close_issue(url, binding, integrated, submission):
    repository = binding['repository'].removesuffix('.git').replace('git@github.com:', 'https://github.com/').rstrip('/')
    revision = integrated['revision']
    commit = repository + '/commit/' + revision if repository.startswith('https://github.com/') else revision
    body = 'Commit: ' + commit + '\n\n' + submission['summary']
    if submission.get('answer'):
        body += '\n\n' + submission['answer']
    issue = json.loads(run('gh', 'issue', 'view', url, '--json', 'state,comments'))
    # A comment may have succeeded before an interrupted close; reconcile it first.
    if not any(row['body'] == body for row in issue['comments']):
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8') as stream:
            stream.write(body)
            stream.flush()
            run('gh', 'issue', 'comment', url, '--body-file', stream.name)
    if issue['state'] != 'CLOSED':
        run('gh', 'issue', 'close', url, '--reason', 'completed')
    if json.loads(run('gh', 'issue', 'view', url, '--json', 'state'))['state'] != 'CLOSED':
        raise ValueError('The linked GitHub issue did not close; resume integration to retry.')
