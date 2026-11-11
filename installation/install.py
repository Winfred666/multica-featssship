#!/usr/bin/env python3
"""README installer: edit one config, then install after human confirmation."""
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

from common import PROCESS_KEY, QUESTIONS, check_repo, cli, exclude_local, feature_branch, installation_config, merge_patch, repo_root, save_config
from packages import bind, build, install

START, END = '<!-- featssship:installation -->', '<!-- /featssship:installation -->'


def section(original, text):
    addition = START + '\n' + text + '\n' + END
    pattern = re.escape(START) + r'.*?' + re.escape(END)
    return re.sub(pattern, lambda _: addition, original or '', flags=re.S) if START in (original or '') else (original or '').rstrip() + '\n\n' + addition


def defaults(issue):
    source = cli('agent', 'get', issue['assignee_id'])
    settings = {key: source.get(key, '') for key in ('runtime_id', 'model', 'thinking_level')}
    template = {'repository': '', 'manual': False,
                **{role: {'name': 'Featssship ' + label, **settings}
                   for role, label in (('delegator', 'Delegator'), ('developer', 'Developer'), ('reviewer', 'Reviewer'))},
                'directions': [{'name': 'main', 'scope': '.', 'questions': list(QUESTIONS),
                                'test_command': '', 'branch_prefix': 'feat/main'}]}
    config = installation_config(issue) or template
    config.setdefault('manual', False)
    # Upgrade the previous installer record in place; never retain issue pointers.
    for old, new in (('main', 'delegator'), ('main_id', 'installed_delegator_id'),
                     ('installed_main_id', 'installed_delegator_id')):
        value = config.pop(old, None)
        if value is not None:
            config.setdefault(new, value)
    for role in ('delegator', 'developer', 'reviewer'):
        old = config.pop(role + '_id', None)
        if old:
            config.setdefault('installed_' + role + '_id', old)
    for key in ('root_issue_id', 'installation_issue_id', 'workspace_id', 'project_id', 'branch'):
        config.pop(key, None)
    for key in ('feature_skill_id', 'delegation_skill_id'):
        if key in config:
            config['installed_' + key] = config.pop(key)
    for direction in config['directions']:
        if 'question' in direction:
            direction['questions'] = [direction.pop('question'), *QUESTIONS]
    return config


def validate(config):
    if not isinstance(config.get('manual', False), bool):
        raise ValueError('manual must be true or false.')
    def required(data, key):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(key + ' is required; fill the installation config before confirming.')
    required(config, 'repository')
    if not isinstance(config.get('directions'), list) or not config['directions']:
        raise ValueError('Configure at least one direction.')
    names = set()
    for direction in config['directions']:
        for key in ('name', 'scope', 'test_command'):
            required(direction, key)
        questions = direction.get('questions')
        if not isinstance(questions, list) or not questions or any(not isinstance(q, str) or not q.strip() for q in questions):
            raise ValueError('Direction questions must be a nonempty list of strings.')
        direction.setdefault('branch_prefix', 'feat/' + direction['name'])
        feature_branch(direction, 'example')
        if direction['name'] in names:
            raise ValueError('Direction names must be distinct.')
        names.add(direction['name'])
    for role in ('delegator', 'developer', 'reviewer'):
        if not (config.get('installed_' + role + '_id') or config.get(role, {}).get('id')):
            for key in ('name', 'runtime_id'):
                required(config.get(role, {}), key)
            if not isinstance(config[role].get('model'), str):
                raise ValueError(role + '.model must be a string; blank inherits the runtime default.')
    ids = [config.get('installed_' + role + '_id') or config.get(role, {}).get('id') for role in ('delegator', 'developer', 'reviewer')]
    selected = [identity for identity in ids if identity]
    if len(set(selected)) != len(selected):
        raise ValueError('Select distinct MAIN, Developer and Reviewer agents.')


def agent(config, role, issue):
    key = 'installed_' + role + '_id'
    selected = config.get(key) or config.get(role, {}).get('id')
    if not selected:
        settings = config[role]
        instructions = {'delegator': 'Only draft and delegate features with the installed featssship skill, then receive results.',
                        'developer': 'Implement, test and submit for independent review with the installed featssship skill.',
                        'reviewer': 'Only read the submitted revision and return approval or corrections with the installed featssship skill; do not edit, test, merge or push.'}
        words = ['agent', 'create', '--name', settings['name'], '--runtime-id', settings['runtime_id'],
                 '--model', settings['model'], '--instructions', instructions[role]]
        if settings.get('thinking_level'):
            words += ['--thinking-level', settings['thinking_level']]
        created = cli(*words)
        selected = created['id']
        config[key] = selected
        save_config(issue['id'], config)
    data = cli('agent', 'get', selected)
    if not data.get('runtime_id') or data.get('workspace_id') != issue['workspace_id']:
        raise ValueError('Select an agent bound to a runtime in the target workspace.')
    config[key] = selected
    save_config(issue['id'], config)
    return selected


def main_root(config, issue):
    children = cli('issue', 'children', issue['id'])
    rows = children['unstaged'] + [child for stage in children['stages'] for child in stage['issues']]
    roots = [row for row in rows if row['title'].startswith('MAIN DEV:') and row['status'] != 'cancelled']
    if len(roots) > 1:
        raise ValueError('Installation has more than one MAIN child; select the intended child before continuing.')
    if roots:
        root = roots[0]
        config['installed_delegator_id'] = root['assignee_id']
        agent(config, 'delegator', issue)
    else:
        main = agent(config, 'delegator', issue)
        root = cli('issue', 'create', '--title', 'MAIN DEV: Ship features for ' + config['repository'],
                   '--description-stdin', '--parent', issue['id'], '--project', issue['project_id'],
                   '--assignee-id', main, '--status', 'backlog',
                   input='MAIN delegates features and receives verified results.')
    cli('issue', 'subscriber', 'add', root['id'], '--user', 'CEO')
    return root


def execute(config, issue):
    validate(config)
    repo = repo_root()
    check_repo(repo, config)
    if not issue.get('project_id'):
        config['installed_project_id'] = config.get('installed_project_id') or cli('project', 'create', '--title', config['repository'].rstrip('/').rsplit('/', 1)[-1].removesuffix('.git'), '--repo', config['repository'])['id']
        save_config(issue['id'], config)
        cli('issue', 'update', issue['id'], '--project', config['installed_project_id'], '--no-start')
        issue['project_id'] = config['installed_project_id']
    config.update(installed_workspace_id=issue['workspace_id'], installed_project_id=issue['project_id'])
    save_config(issue['id'], config)
    root = main_root(config, issue)
    project = cli('project', 'get', issue['project_id'])
    if root['workspace_id'] != issue['workspace_id'] or root['project_id'] != issue['project_id'] or project['workspace_id'] != issue['workspace_id']:
        raise ValueError('The selected root and project must belong to the target workspace/project.')
    if root.get('assignee_type') != 'agent':
        raise ValueError('The MAIN root must be assigned to a MAIN agent.')
    developer = agent(config, 'developer', issue)
    reviewer = agent(config, 'reviewer', issue)
    if developer == reviewer or root['assignee_id'] in (developer, reviewer):
        raise ValueError('Select distinct MAIN, Developer and Reviewer agents so MAIN only dispatches and receives.')
    exclude_local(repo)
    local = repo / '.multica' / 'featssship' / 'packages'
    feature_package = build('feature', local / 'multica-featssship-develop-review')
    config['installed_feature_skill_id'] = install(feature_package, config.get('installed_feature_skill_id'))
    save_config(issue['id'], config)
    for identity in (developer, reviewer):
        bind(identity, config['installed_feature_skill_id'])
    name = 'multica-featssship-' + issue['project_id'][:8]
    root_package = build('delegation', local / name, name=name)
    config['installed_delegation_skill_id'] = install(root_package, config.get('installed_delegation_skill_id'))
    save_config(issue['id'], config)
    bind(root['assignee_id'], config['installed_delegation_skill_id'])
    # Remove only the old installer's owned block, preserving project context.
    project_text = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', project.get('description') or '', flags=re.S)
    init_text = 'Repository: ' + config['repository'] + '\n\n' + '\n'.join(
        f"- {d['name']}: {d['scope']}\n  Test: `{d['test_command']}`" for d in config['directions'])
    project_text = section(project_text, init_text)
    if project_text != project.get('description'):
        cli('project', 'update', project['id'], '--description', project_text)
    root_text = section(root.get('description'),
                        'MAIN drafts and delegates features. '
                        'Developer implements and owns approved integration; Reviewer only returns a verdict.\n\nRun `' + shlex.join(['python3', str(repo / '.agents/skills' / name / 'wrapper.py')]) + '` from the target repository root.')
    title = 'MAIN DEV: ' + re.sub(r'^(?:MAIN DEV:\s*)+', '', root['title'])
    cli('issue', 'update', root['id'], '--title', title, '--description-stdin', '--no-start', input=root_text)
    destination = repo / '.agents' / 'skills'
    for package in (feature_package, root_package):
        target = destination / package.name
        ignored = ['.state', '__pycache__', '.errors']
        if (target / 'config.json').exists():
            ignored.append('config.json')
        shutil.copytree(package, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*ignored))
        (target / 'DEBUG.md').unlink(missing_ok=True)
        (target / 'installation.json').unlink(missing_ok=True)
        for obsolete in (target / 'roles').glob('*-debug.md'):
            obsolete.unlink()
    save_config(root['id'], {'manual': config.get('manual', False), 'directions': {d['name']: {key: d[key] for key in ('questions', 'branch_prefix')}
                                                   for d in config['directions']}}, PROCESS_KEY)
    if installation_config(root):
        cli('issue', 'metadata', 'delete', root['id'], '--key', 'featssship.installation')
    save_config(issue['id'], config)
    command = shlex.join(['python3', str(destination / name / 'wrapper.py')])
    return {'root_issue_id': root['id'], 'developer_id': developer, 'reviewer_id': reviewer,
            'command': command, 'inputs': '--thread REQUEST_UUID --config <request-config-JSON>'}


if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, str(Path(__file__).with_name('wrapper.py')), *sys.argv[1:]]))
