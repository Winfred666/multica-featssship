"""Native CLI, comment records and Git operations shared by the local skills."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

QUESTIONS = (
    'Does the delivered behavior satisfy the request and acceptance evidence?',
    'Are the additions necessary for the requested outcome?',
    'Does the solution preserve the requested demand without shifting scope?',
)


def run(*words, cwd=None, input=None):
    result = subprocess.run(words, cwd=cwd, input=input, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or str(words))
    return result.stdout.strip()


def cli(*words, input=None):
    return json.loads(run('multica', *words, '--output', 'json', input=input))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        json.dump(data, stream, indent=2)
        temporary = Path(stream.name)
    temporary.replace(path)


def block(kind, data):
    return f'<!-- featssship:{kind} -->\n```json\n{json.dumps(data, indent=2)}\n```'


def unpack(content, kind):
    match = re.search(r'<!-- featssship:' + re.escape(kind) + r' -->\s*```json\n(.*?)\n```', content, re.S)
    return json.loads(match[1]) if match else None


def comment(issue_id, content, parent=None):
    words = ['issue', 'comment', 'add', issue_id, '--content-stdin']
    if parent:
        words += ['--parent', parent]
    return cli(*words, input=content)


def mention(agent_id):
    return f'[@agent](mention://agent/{agent_id})'


def reply_parent(context, fallback):
    return getattr(context['args'], 'thread', None) or context['state'].get('reply_parent') or fallback


def check_identity(context, binding, role):
    if context['workspace_id'] != binding['workspace_id'] or context['issue_id'] != binding['issue_id']:
        raise ValueError('Use this package in its native workspace and issue.')
    if context['agent_id'] != binding[role + '_id']:
        raise ValueError('This action belongs to the configured ' + role + ' identity.')
    if binding['developer_id'] == binding['reviewer_id']:
        raise ValueError('Developer and Reviewer must be different identities.')


def feature(context, role='developer'):
    issue = cli('issue', 'get', context['issue_id'])
    binding = unpack(issue['description'], 'binding')
    if not binding:
        raise ValueError('This issue has no featssship binding.')
    check_identity(context, binding, role)
    if issue.get('status_category') in ('done', 'cancelled'):
        raise ValueError('The feature issue is closed.')
    return issue, binding


def records(binding):
    rows = cli('issue', 'comment', 'list', binding['issue_id'], '--thread', binding['thread_id'], '--tail', '30')
    found = []
    for row in rows:
        for kind, role in (('submission', 'developer'), ('review', 'reviewer'), ('integration-rework', 'developer'), ('integration', 'developer'), ('result', 'developer')):
            data = unpack(row.get('content', ''), kind)
            if data and row.get('author_type') == 'agent' and row.get('author_id') == binding[role + '_id']:
                found.append((kind, data, row))
    return found, rows


def latest(rows, kind):
    return next(((data, row) for key, data, row in reversed(rows) if key == kind), (None, None))


def current(binding):
    rows, comments = records(binding)
    submission, submit_row = latest(rows, 'submission')
    review, review_row = latest(rows, 'review')
    # A verdict belongs to one submission, even if Developer resubmits the same SHA.
    if review and (not submit_row or review['submission_id'] != submit_row['id']):
        review, review_row = None, None
    correction, correction_row = latest(rows, 'integration-rework')
    if correction and submission and correction.get('submission_id') == submit_row['id']:
        review, review_row = {**correction, 'verdict': 'rework'}, correction_row
    return submission, submit_row, review, review_row, rows, comments


def repo_root():
    return Path(run('git', 'rev-parse', '--show-toplevel')).resolve()


def git(repo, *words):
    return run('git', '-C', str(repo), *words)


def clean(repo):
    if git(repo, 'status', '--porcelain'):
        raise ValueError('Commit or preserve the checkout changes before this action.')


def check_repo(repo, binding):
    def slug(url):
        return url.removesuffix('.git').replace('git@github.com:', 'https://github.com/').rstrip('/')
    if slug(git(repo, 'remote', 'get-url', 'origin')) != slug(binding['repository']):
        raise ValueError('Run from the configured target repository root.')


def exclude_local(repo):
    path = Path(git(repo, 'rev-parse', '--git-path', 'info/exclude'))
    if not path.is_absolute():
        path = repo / path
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else ''
    for pattern in ('/.multica/featssship/', '/.agents/skills/multica-featssship*/'):
        if pattern not in existing.splitlines():
            existing += '\n' + pattern + '\n'
    path.write_text(existing)


def test(repo, command, *, required=True):
    result = subprocess.run(command, shell=True, cwd=repo, text=True, capture_output=True)
    evidence = {'command': command, 'exit_code': result.returncode,
                'output': (result.stdout + result.stderr)[-4000:]}
    if result.returncode and required:
        raise ValueError('Configured check failed: ' + json.dumps(evidence))
    clean(repo)
    return evidence


def human_accepts(comments, commit):
    return any(row.get('author_type') == 'member' and
               unpack(row.get('content', ''), 'accept') == {'commit': commit} for row in comments)


def has_manual(issue):
    return any(label['name'] == 'manual' for label in issue.get('labels', []))


def entry_command(name):
    return f'From the target repository root, run python3 <installed {name} skill directory>/entry.py, then follow its returned commands.'
