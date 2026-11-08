#!/usr/bin/env python3
"""One-time README installation; answers and successful IDs persist after each write."""
import argparse
import json
from pathlib import Path
import re
import shlex

from common import check_repo, cli, entry_command, exclude_local, repo_root, write_json
from packages import bind, build, install

START, END = '<!-- featssship:installation -->', '<!-- /featssship:installation -->'


def section(original, text):
    addition = START + '\n' + text + '\n' + END
    pattern = re.escape(START) + r'.*?' + re.escape(END)
    return re.sub(pattern, lambda _: addition, original or '', flags=re.S) if START in (original or '') else (original or '').rstrip() + '\n\n' + addition


def ask(config, key, prompt):
    if key not in config:
        config[key] = input(prompt + ': ').strip()
    if not str(config[key]).strip():
        raise ValueError(key + ' is required')
    return config[key]


def configure(config, path):
    for key, prompt in (('workspace_id', 'Workspace UUID'), ('project_id', 'Project UUID'),
                        ('root_issue_id', 'Existing MAIN root issue UUID'), ('repository', 'Target Git repository URL')):
        ask(config, key, prompt)
    if 'directions' not in config:
        config['directions'] = []
        count = int(input('Number of concurrent directions: '))
        for _ in range(count):
            direction = {}
            for key in ('name', 'scope', 'question', 'test_command'):
                ask(direction, key, 'Direction ' + key)
            config['directions'].append(direction)
    if not config['directions']:
        raise ValueError('Configure at least one direction.')
    names = set()
    for direction in config['directions']:
        for key in ('name', 'scope', 'question', 'test_command'):
            ask(direction, key, 'Direction ' + key)
        if direction['name'] in names:
            raise ValueError('Direction names must be distinct.')
        names.add(direction['name'])
    if config.get('developer_id') and config.get('developer_id') == config.get('reviewer_id'):
        raise ValueError('Developer and Reviewer must be distinct.')
    write_json(path, config)


def agent(config, role, path):
    key = role + '_id'
    if not config.get(key):
        if role not in config:
            selected = input(f'Existing {role} UUID (blank to create): ').strip()
            if selected:
                config[key] = selected
            else:
                config[role] = {}
        if not config.get(key):
            settings = config[role]
            for field in ('name', 'runtime_id', 'model'):
                ask(settings, field, role + ' ' + field)
            write_json(path, config)
            settings_text = ('Use the repository-owned multica-featssship procedures supplied by the issue. '
                             'Follow the returned callbacks under your native task ID. '
                             'Keep human manual holds. MAIN dispatches and receives only. ')
            settings_text += ('Implement and integrate only after independent Reviewer approval.' if role == 'developer' else
                              'Inspect the submitted revision independently, leave source unchanged, and approve or return corrections.')
            created = cli('agent', 'create', '--name', settings['name'], '--runtime-id', settings['runtime_id'],
                          '--model', settings['model'], '--instructions', settings_text)
            config[key] = created['id']
            write_json(path, config)
    data = cli('agent', 'get', config[key])
    if not data.get('runtime_id') or data.get('workspace_id') != config['workspace_id']:
        raise ValueError('Select an agent bound to a runtime in the target workspace.')
    write_json(path, config)
    return config[key]


def execute(config, path):
    configure(config, path)
    root = cli('issue', 'get', config['root_issue_id'])
    project = cli('project', 'get', config['project_id'])
    if root['workspace_id'] != config['workspace_id'] or root['project_id'] != config['project_id'] or project['workspace_id'] != config['workspace_id']:
        raise ValueError('The selected root and project must belong to the target workspace/project.')
    if root.get('assignee_type') != 'agent':
        raise ValueError('Select an existing MAIN root assigned to an agent.')
    repo = repo_root()
    check_repo(repo, config)
    config['main_id'] = root['assignee_id']
    developer = agent(config, 'developer', path)
    reviewer = agent(config, 'reviewer', path)
    if developer == reviewer or config['main_id'] in (developer, reviewer):
        raise ValueError('Select distinct MAIN, Developer and Reviewer agents so MAIN only dispatches and receives.')
    exclude_local(repo)
    config['branch'] = 'main'
    local = repo / '.multica' / 'featssship' / 'packages'
    developer_package = build('developer', local / 'multica-featssship-developer')
    config['developer_skill_id'] = install(developer_package, config.get('developer_skill_id'))
    write_json(path, config)
    bind(developer, config['developer_skill_id'])
    name = 'multica-featssship-' + config['project_id'][:8]
    root_package = build('delegation', local / name, name=name, binding=config)
    config['delegation_skill_id'] = install(root_package, config.get('delegation_skill_id'))
    write_json(path, config)
    bind(config['main_id'], config['delegation_skill_id'])
    directions = '\n\n'.join(f"- {d['name']}: {d['scope']}\n  Acceptance: {d['question']}\n  Test: `{d['test_command']}`" for d in config['directions'])
    project_text = section(project.get('description'), 'Concurrent directions\n\n' + directions)
    cli('project', 'update', project['id'], '--description', project_text)
    root_text = section(root.get('description'),
                        'MAIN delegates a feature/fix request with its direction and acceptance question, then receives one verified result. '
                        'Developer owns implementation and approved integration; the distinct Reviewer owns acceptance.\n\n' + directions + '\n\n' + entry_command(name))
    title = 'MAIN DEV: ' + re.sub(r'^(?:MAIN DEV:\s*)+', '', root['title'])
    cli('issue', 'update', root['id'], '--title', title, '--description-stdin', '--no-start', input=root_text)
    destination = repo / '.agents' / 'skills'
    import shutil
    for package in (developer_package, root_package):
        shutil.copytree(package, destination / package.name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.state', '__pycache__', '.errors'))
    command = shlex.join(['python3', str(destination / name / 'wrapper.py')])
    return {'root_issue_id': root['id'], 'developer_id': developer, 'reviewer_id': reviewer,
            'command': command, 'inputs': 'dispatch --title TITLE --request REQUEST --direction NAME [--question QUESTION]'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True, help='Ignored JSON answers and owned IDs; updated after successful writes')
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config.exists() else {}
    print(json.dumps(execute(config, args.config), indent=2))
