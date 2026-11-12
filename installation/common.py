"""Native CLI, comment records and Git operations shared by the local skills."""
import json
from pathlib import Path
import re
import subprocess
import tempfile

# TODO: Runtime-enforced completion belongs to https://github.com/Winfred666/multica-RSI/issues/40.
ROUND_DONE = 'Delivery done this round, directly and silently end this turn'
REWORK_DONE = 'Rework sent, directly and silently end this turn'
WAIT_OUTER = 'Directly and silently end this turn if outer confirmation has not been received yet.'
CONFIG_KEY = 'featssship.config'
DELEGATION_KEY = 'featssship.delegation'
DISPATCH_KEY = 'featssship.dispatch'


def config_ref(issue, key=CONFIG_KEY):
    value = issue.get('metadata', {}).get(key)
    return json.loads(value) if isinstance(value, str) else value


def link_config(issue_id, reference, key=CONFIG_KEY):
    cli('issue', 'metadata', 'set', issue_id, '--key', key,
        '--value', json.dumps(reference), '--type', 'string')


def attachment(reference):
    owner = cli('issue', 'get', reference['issue_id'])
    rows = [row for row in owner.get('attachments', []) if row['filename'] == reference['filename']]
    if not rows:
        raise ValueError('Configuration attachment is missing: ' + json.dumps(reference))
    return max(rows, key=lambda row: (row.get('created_at', ''), row['id']))


def download_config(reference, directory):
    # TODO: Replace download/read with native deliverable preview when supported.
    row = attachment(reference)
    downloaded = json.loads(run('multica', 'attachment', 'download', row['id'], '--output-dir', str(directory)))
    return Path(downloaded['path'])


def read_config(reference):
    with tempfile.TemporaryDirectory(prefix='.featssship-', dir=Path.cwd()) as directory:
        return json.loads(download_config(reference, directory).read_text())


def write_config(reference, config, parent=None, message=' '):
    return write_artifact(reference, json.dumps(config, indent=2) + '\n', parent, message)


def write_artifact(reference, content, parent=None, message=' '):
    # TODO: Replace immutable attachment revisions with native deliverable update.
    # The stable owner/filename reference resolves the newest revision, across issues.
    if not parent:
        roots = cli('issue', 'comment', 'list', reference['issue_id'], '--roots-only', '--summary')
        parent = roots[-1]['id'] if roots else None
    with tempfile.TemporaryDirectory(prefix='.featssship-', dir=Path.cwd()) as directory:
        path = Path(directory) / reference['filename']
        path.write_text(content)
        # Grilling supplies a confirmation prompt; other revisions render empty.
        words = ['issue', 'comment', 'add', reference['issue_id'], '--content', message, '--attachment', str(path)]
        if parent:
            words += ['--parent', parent]
        return cli(*words)


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


def request_config(batch, installed=None, *, index):
    """Resolve one batch item against live universal settings."""
    config = {key: value for key, value in batch.items() if key != 'issues'}
    config.update(batch['issues'][index])
    installed = installed if installed is not None else read_config(config['source'])
    directions = installed['directions']
    name = config.get('direction', directions[0]['name'] if len(directions) == 1 else None)
    selected = next((d for d in directions if d['name'] == name), {})
    result = {key: installed[key] for key in ('repository', 'sandbox') if key in installed}
    result.update(parent_branch=installed.get('parent_branch', 'main'), manual=installed.get('manual', False),
                  **{role + '_id': installed.get('installed_' + role + '_id') for role in ('delegator', 'developer', 'reviewer')},
                  direction=name, scope=selected.get('scope', ''),
                  question=next(iter(selected.get('questions', [])), ''))
    result.update(config)
    result['questions'] = config.get('questions', [result['question'], *[q for q in selected.get('questions', []) if q != result['question']]])
    if selected and result.get('name'):
        result.setdefault('branch', feature_branch(selected, result['name']))
    return result


def delegation_config(installed, batch, source, main_issue_id, dispatch_thread):
    document = {'source': source, 'main_issue_id': main_issue_id,
                'dispatch_thread': dispatch_thread, 'issues': [dict(item) for item in batch['issues']]}
    for index, item in enumerate(document['issues']):
        resolved = request_config(document, installed, index=index)
        for key in ('direction', 'branch'):
            if resolved.get(key):
                item[key] = resolved[key]
    return document


def feature_config(issue):
    reference = config_ref(issue, DELEGATION_KEY)
    if not reference:
        raise ValueError('MAIN must link the delegation configuration before development.')
    config = request_config(read_config(reference), index=reference['index'])
    name = config['direction']
    project = cli('project', 'get', issue['project_id'])
    section = re.search(r'<!-- featssship:installation -->(.*?)<!-- /featssship:installation -->',
                        project.get('description', ''), re.S)
    command = re.search(r'^- ' + re.escape(name) + r':.*\n  Test: `(.*)`$', section[1] if section else '', re.M)
    if not command or not command[1].strip():
        raise ValueError('Project description needs verification guidance for direction ' + name)
    return {**config, 'test_command': command[1]}


def run(*words, cwd=None, input=None):
    result = subprocess.run(words, cwd=cwd, input=input, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or str(words))
    return result.stdout.strip()


def cli(*words, input=None):
    return json.loads(run('multica', *words, '--output', 'json', input=input))


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


def mention(agent_id):
    name = cli('agent', 'get', agent_id)['name']
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
