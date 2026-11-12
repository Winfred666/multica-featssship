#!/usr/bin/env python3
"""README installer: edit one config, then install after human confirmation."""
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

from common import check_repo, cli, config_ref, exclude_local, feature_branch, link_config, repo_root, write_config
from packages import bind, build, install

START, END = '<!-- featssship:installation -->', '<!-- /featssship:installation -->'


def section(original, text):
    addition = START + '\n' + text + '\n' + END
    pattern = re.escape(START) + r'.*?' + re.escape(END)
    return re.sub(pattern, lambda _: addition, original or '', flags=re.S) if START in (original or '') else (original or '').rstrip() + '\n\n' + addition


def defaults(issue):
    source = cli('agent', 'get', issue['assignee_id'])
    settings = {key: source.get(key, '') for key in ('runtime_id', 'model', 'thinking_level')}
    return {'repository': '', 'parent_branch': 'main', 'manual': False,
            **{role: {'name': 'Featssship ' + label, **settings}
               for role, label in (('delegator', 'Delegator'), ('developer', 'Developer'), ('reviewer', 'Reviewer'))},
            'directions': [{'name': 'main', 'scope': '.', 'questions': [],
                            'test_command': '', 'branch_prefix': 'feat/main'}]}


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


def agent(config, role, issue, state):
    key = 'installed_' + role + '_id'
    selected = config.get(key) or config.get(role, {}).get('id')
    if not selected:
        settings = config[role]
        instructions = {'delegator': 'Only draft and delegate features with the installed featssship skill, then receive results.',
                        'developer': 'Own only development: implement, test, correct and submit with the installed featssship skill.',
                        'reviewer': 'Review the submitted revision, then own approval, scripted integration, push and completion with the installed featssship skill; return source corrections to Developer.'}
        words = ['agent', 'create', '--name', settings['name'], '--runtime-id', settings['runtime_id'],
                 '--model', settings['model'], '--instructions', instructions[role]]
        if settings.get('thinking_level'):
            words += ['--thinking-level', settings['thinking_level']]
        created = cli(*words)
        selected = created['id']
    if config.get(key) != selected:
        config[key] = selected
        write_config(config_ref(issue), config, state.get('reply_parent'))
    data = cli('agent', 'get', selected)
    if not data.get('runtime_id') or data.get('workspace_id') != issue['workspace_id']:
        raise ValueError('Select an agent bound to a runtime in the target workspace.')
    return selected


def main_root(config, issue, state, save_state):
    if state.get('main_issue_id'):
        root = cli('issue', 'get', state['main_issue_id'])
        config['installed_delegator_id'] = root['assignee_id']
        agent(config, 'delegator', issue, state)
    else:
        main = agent(config, 'delegator', issue, state)
        root = cli('issue', 'create', '--title', 'MAIN DEV: Ship features for ' + config['repository'],
                   '--description-stdin', '--project', issue['project_id'], '--allow-duplicate',
                   '--assignee-id', main, '--status', 'backlog',
                   input='MAIN delegates features and receives verified results.')
        state['main_issue_id'] = root['id']
        save_state()
    cli('issue', 'subscriber', 'add', root['id'], '--user', 'CEO')
    return root


def execute(config, issue, state, save_state):
    validate(config)
    repo = repo_root()
    check_repo(repo, config)
    if not issue.get('project_id'):
        state['project_id'] = state.get('project_id') or cli('project', 'create', '--title', config['repository'].rstrip('/').rsplit('/', 1)[-1].removesuffix('.git'), '--repo', config['repository'])['id']
        save_state()
        cli('issue', 'update', issue['id'], '--project', state['project_id'], '--no-start')
        issue['project_id'] = state['project_id']
    root = main_root(config, issue, state, save_state)
    link_config(root['id'], config_ref(issue))
    project = cli('project', 'get', issue['project_id'])
    if root['workspace_id'] != issue['workspace_id'] or root['project_id'] != issue['project_id'] or project['workspace_id'] != issue['workspace_id']:
        raise ValueError('The selected root and project must belong to the target workspace/project.')
    if root.get('assignee_type') != 'agent':
        raise ValueError('The MAIN root must be assigned to a MAIN agent.')
    developer = agent(config, 'developer', issue, state)
    reviewer = agent(config, 'reviewer', issue, state)
    if developer == reviewer or root['assignee_id'] in (developer, reviewer):
        raise ValueError('Select distinct MAIN, Developer and Reviewer agents so MAIN only dispatches and receives.')
    exclude_local(repo)
    local = repo / '.multica' / 'featssship' / 'packages'
    feature_package = build('feature', local / 'multica-featssship-develop-review')
    config['installed_feature_skill_id'] = install(feature_package, config.get('installed_feature_skill_id'))
    write_config(config_ref(issue), config, state.get('reply_parent'))
    for identity in (developer, reviewer):
        bind(identity, config['installed_feature_skill_id'])
    name = 'multica-featssship-' + issue['project_id'][:8]
    root_package = build('delegation', local / name, name=name)
    config['installed_delegation_skill_id'] = install(root_package, config.get('installed_delegation_skill_id'))
    write_config(config_ref(issue), config, state.get('reply_parent'))
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
                        'Developer implements and tests; Reviewer owns review, approved integration and completion.\n\nRun `' + shlex.join(['python3', str(repo / '.agents/skills' / name / 'wrapper.py')]) + '` from the target repository root.')
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
    command = shlex.join(['python3', str(destination / name / 'wrapper.py')])
    return {'root_issue_id': root['id'], 'developer_id': developer, 'reviewer_id': reviewer,
            'command': command, 'inputs': '--thread REQUEST_UUID --config <batch-issues-JSON>'}


if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, str(Path(__file__).with_name('wrapper.py')), *sys.argv[1:]]))
