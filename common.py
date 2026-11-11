"""Native CLI, comment records and Git operations shared by the local skills."""
import json
from pathlib import Path
import re
import subprocess

# TODO: Runtime-enforced completion belongs to https://github.com/Winfred666/multica-RSI/issues/40.
ROUND_DONE = 'Delivery/review/work done this round, exit directly and silently'
REWORK_DONE = 'Rework sent, directly and silently exit'
WAIT_OUTER = 'Directly and silently exit if outer confirmation has not been received yet.'
INSTALLATION_KEY = 'featssship.installation'
PROCESS_KEY = 'featssship.process'


def installation_config(issue, key=INSTALLATION_KEY):
    value = issue.get('metadata', {}).get(key, {})
    return json.loads(value) if isinstance(value, str) else value


def process_config(issue):
    return installation_config(issue, PROCESS_KEY)


def save_config(issue_id, config, key=INSTALLATION_KEY):
    cli('issue', 'metadata', 'set', issue_id, '--key', key, '--value', json.dumps(config), '--type', 'string')


def merge_patch(config, patch):
    """JSON merge patch: objects merge, arrays replace, null deletes a field."""
    result = dict(config)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict):
            result[key] = merge_patch(result.get(key, {}) if isinstance(result.get(key), dict) else {}, value)
        else:
            result[key] = value
    return result


def installer_config(main):
    return installation_config(cli('issue', 'get', process_config(main)['installation_issue_id']))


def feature_config(issue):
    process = process_config(issue)
    if not process:
        raise ValueError('MAIN must supply the issue’s process configuration before development.')
    main = cli('issue', 'get', process['main_issue_id'])
    installed = installer_config(main)
    directions = process_config(main)['directions']
    name = next(name for name, direction in directions.items()
                if process['branch'].rsplit('/', 1)[0] == direction['branch_prefix'])
    project = cli('project', 'get', issue['project_id'])
    section = re.search(r'<!-- featssship:installation -->(.*?)<!-- /featssship:installation -->',
                        project.get('description', ''), re.S)
    command = re.search(r'^- ' + re.escape(name) + r':.*\n  Test: `(.*)`$', section[1] if section else '', re.M)
    if not command or not command[1].strip():
        raise ValueError('Project description needs verification guidance for direction ' + name)
    return {**process, 'repository': installed['repository'], 'test_command': command[1],
            **{role + '_id': installed['installed_' + role + '_id'] for role in ('developer', 'reviewer')}}


def run(*words, cwd=None, input=None):
    result = subprocess.run(words, cwd=cwd, input=input, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or str(words))
    return result.stdout.strip()


def cli(*words, input=None):
    return json.loads(run('multica', *words, '--output', 'json', input=input))


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
    result = cli(*words, input=content)
    if steer_agent and any(row['target_id'] == steer_agent and row['status'] == 'blocked'
                           for row in result.get('trigger_outcomes', [])):
        raise ValueError('Comment posted but recipient delivery was blocked; inspect trigger_outcomes before retrying: ' + json.dumps(result))
    return result


def mention(agent_id, name=None):
    name = name or cli('agent', 'get', agent_id)['name']
    return f'[@{name}](mention://agent/{agent_id})'


def repo_root():
    return Path(run('git', 'rev-parse', '--show-toplevel')).resolve()


def git(repo, *words):
    return run('git', '-C', str(repo), *words)


def feature_branch(direction, name):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
        raise ValueError('Give a short kebab-case feature name, such as tree-horizontal-more.')
    branch = (direction.get('branch_prefix') or 'feat/' + direction['name']) + '/' + name
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
