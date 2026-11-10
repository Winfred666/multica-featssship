"""Native CLI, comment records and Git operations shared by the local skills."""
import json
from pathlib import Path
import re
import subprocess
import tempfile

QUESTIONS = (
    'Does the solution preserve the requested demand without shifting scope?',
    'Are the additions necessary for the requested outcome?',
)
# TODO: Runtime-enforced completion belongs to https://github.com/Winfred666/multica-RSI/issues/40.
ROUND_DONE = 'Delivery/review/work done this round, exit directly and silently'


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


def comment(issue_id, content, parent=None, *, steer_agent=None):
    words = ['issue', 'comment', 'add', issue_id, '--content-stdin']
    if parent:
        words += ['--parent', parent]
    if steer_agent:
        for row in cli('issue', 'runs', issue_id, '--active'):
            if (row['agent_id'] == steer_agent and row['status'] == 'running'
                    and row.get('can_supplement') is True):
                words += ['--steer', row['id']]
                break
    return cli(*words, input=content)


def mention(agent_id):
    return f'[@agent](mention://agent/{agent_id})'


def repo_root():
    return Path(run('git', 'rev-parse', '--show-toplevel')).resolve()


def git(repo, *words):
    return run('git', '-C', str(repo), *words)


def feature_branch(direction, name):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
        raise ValueError('Give a short kebab-case feature name, such as tree-horizontal-more.')
    branch = direction.get('branch_prefix', 'feat/' + direction['name']) + '/' + name
    run('git', 'check-ref-format', '--branch', branch)
    return branch


def clean(repo):
    if git(repo, 'status', '--porcelain'):
        raise ValueError('Commit or preserve working-tree changes before this action.')


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


def test(repo, command):
    result = subprocess.run(command, shell=True, cwd=repo, text=True, capture_output=True)
    evidence = {'command': command, 'exit_code': result.returncode,
                'output': (result.stdout + result.stderr)[-4000:]}
    if result.returncode:
        raise ValueError('Configured check failed: ' + json.dumps(evidence))
    if not result.returncode:
        del evidence['output']
    clean(repo)
    return evidence


def has_manual(issue):
    return any(label['name'] == 'manual' for label in issue.get('labels', []))


def entry_command(name):
    return f'Run `python3 <installed {name} skill directory>/wrapper.py` from the target repository root.'
