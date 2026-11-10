#!/usr/bin/env python3
"""Resumable README installation; return one missing question and save owned IDs."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil

from common import check_repo, cli, entry_command, exclude_local, feature_branch, repo_root, write_json
from packages import bind, build, install

START, END = '<!-- featssship:installation -->', '<!-- /featssship:installation -->'


def section(original, text):
    addition = START + '\n' + text + '\n' + END
    pattern = re.escape(START) + r'.*?' + re.escape(END)
    return re.sub(pattern, lambda _: addition, original or '', flags=re.S) if START in (original or '') else (original or '').rstrip() + '\n\n' + addition


class NeedsAnswer(Exception):
    def __init__(self, field, question):
        self.field, self.question = field, question


def ask(config, key, prompt, *, field=None):
    if key not in config:
        raise NeedsAnswer(field or key, prompt)
    if not str(config[key]).strip():
        raise ValueError(key + ' is required')
    return config[key]


def configure(config, path):
    ask(config, 'repository', 'Which target repository needs featssship? Provide its Git URL; '
        'this is where Developer and Reviewer will ship features, not necessarily the featssship source repository.')
    if 'directions' not in config:
        count = int(ask(config, 'direction_count', f'For {config["repository"]}, how many concurrent feature directions '
                        'should featssship configure? Answer with a positive integer; use 1 for a single direction.'))
        if count < 1:
            raise ValueError('Configure at least one direction.')
        config['directions'] = [{} for _ in range(count)]
    if not config['directions']:
        raise ValueError('Configure at least one direction.')
    names = set()
    prompts = {'name': 'What short name identifies this direction?',
               'scope': 'Which files or code area should this direction own?',
               'question': 'What acceptance question should Reviewer answer for this direction?',
               'test_command': 'What command should Developer run to verify this direction?'}
    for index, direction in enumerate(config['directions']):
        for key, prompt in prompts.items():
            context = f'For {config["repository"]}, direction {index + 1} ({direction.get("name", "unnamed")}): '
            if key in ('question', 'test_command'):
                context += f'Scope: {direction["scope"]}. '
            if key == 'test_command':
                context += f'Acceptance: {direction["question"]} '
            ask(direction, key, context + prompt, field=f'directions.{index}.{key}')
        direction.setdefault('branch_prefix', 'feat/' + direction['name'])
        feature_branch(direction, 'example')
        if direction['name'] in names:
            raise ValueError('Direction names must be distinct.')
        names.add(direction['name'])
    if config.get('developer_id') and config.get('developer_id') == config.get('reviewer_id'):
        raise ValueError('Developer and Reviewer must be distinct.')
    write_json(path, config)


def agent(config, role, path):
    key = role + '_id'
    if not config.get(key):
        settings = config.setdefault(role, {})
        settings.setdefault('name', 'Featssship ' + ('MAIN' if role == 'main' else role.title()))
        for field in ('runtime_id', 'model'):
            if field == 'model' and settings.get(field) == '':
                continue  # Explicitly inherit the runtime's default model.
            runtime = f' on runtime {settings["runtime_id"]}' if field == 'model' else ''
            ask(settings, field, f'For {config["repository"]}, which {field.replace("_id", "")} should '
                f'the {role.title()} agent use{runtime}?', field=f'{role}.{field}')
        write_json(path, config)
        instructions = {'main': 'Only draft and delegate features with the installed featssship skill, then receive results.',
                        'developer': 'Implement, test and submit for independent review with the installed featssship skill.',
                        'reviewer': 'Only read the submitted revision and return approval or corrections with the installed featssship skill; do not edit, test, merge or push.'}
        words = ['agent', 'create', '--name', settings['name'], '--runtime-id', settings['runtime_id'],
                 '--model', settings['model'], '--instructions', instructions[role]]
        if settings.get('thinking_level'):
            words += ['--thinking-level', settings['thinking_level']]
        created = cli(*words)
        config[key] = created['id']
        write_json(path, config)
    data = cli('agent', 'get', config[key])
    if not data.get('runtime_id') or data.get('workspace_id') != config['workspace_id']:
        raise ValueError('Select an agent bound to a runtime in the target workspace.')
    write_json(path, config)
    return config[key]


def installation_context(config):
    installation = config.get('installation_issue_id')
    if not installation and not config.get('root_issue_id'):
        installation = os.environ.get('MULTICA_ISSUE_ID')
    issue_id = installation or config.get('root_issue_id')
    if not issue_id:
        raise ValueError('Run installation from its assigned Multica issue; no existing MAIN root is required.')
    issue = cli('issue', 'get', issue_id)
    for key in ('workspace_id', 'project_id'):
        if not issue.get(key) or config.get(key, issue[key]) != issue[key]:
            raise ValueError('Installation context must match its workspace and project.')
        config[key] = issue[key]
    if installation:
        config['installation_issue_id'] = installation
    return issue


def main_root(config, path, installation):
    if config.get('root_issue_id'):
        return cli('issue', 'get', config['root_issue_id'])
    if not config.get('main_id') and 'main' not in config:
        source_id = os.environ.get('MULTICA_AGENT_ID') or installation.get('assignee_id')
        source = cli('agent', 'get', source_id)
        config['main'] = {key: source.get(key, '') for key in ('runtime_id', 'model', 'thinking_level')}
    main = agent(config, 'main', path)
    root = cli('issue', 'create', '--title', 'MAIN DEV: Ship features for ' + config['repository'],
               '--description-stdin', '--parent', config['installation_issue_id'], '--project', config['project_id'],
               '--assignee-id', main, '--status', 'backlog',
               input='Target repository: ' + config['repository'] + '\n\nMAIN delegates features and receives verified results. '
               'Installation context: [installer issue](mention://issue/' + config['installation_issue_id'] + ').')
    config['root_issue_id'] = root['id']
    write_json(path, config)
    return root


def execute(config, path):
    installation = installation_context(config)
    configure(config, path)
    repo = repo_root()
    check_repo(repo, config)
    root = main_root(config, path, installation)
    project = cli('project', 'get', config['project_id'])
    if root['workspace_id'] != config['workspace_id'] or root['project_id'] != config['project_id'] or project['workspace_id'] != config['workspace_id']:
        raise ValueError('The selected root and project must belong to the target workspace/project.')
    if root.get('assignee_type') != 'agent':
        raise ValueError('The MAIN root must be assigned to a MAIN agent.')
    config['main_id'] = root['assignee_id']
    developer = agent(config, 'developer', path)
    reviewer = agent(config, 'reviewer', path)
    if developer == reviewer or config['main_id'] in (developer, reviewer):
        raise ValueError('Select distinct MAIN, Developer and Reviewer agents so MAIN only dispatches and receives.')
    exclude_local(repo)
    config['branch'] = 'main'
    local = repo / '.multica' / 'featssship' / 'packages'
    feature_package = build('feature', local / 'multica-featssship-develop-review')
    config['feature_skill_id'] = install(feature_package, config.get('feature_skill_id'))
    write_json(path, config)
    for identity in (developer, reviewer):
        bind(identity, config['feature_skill_id'])
    name = 'multica-featssship-' + config['project_id'][:8]
    root_package = build('delegation', local / name, name=name, binding=config)
    config['delegation_skill_id'] = install(root_package, config.get('delegation_skill_id'))
    write_json(path, config)
    bind(config['main_id'], config['delegation_skill_id'])
    directions = '\n\n'.join(f"- {d['name']}: {d['scope']}\n  Branch: `{d['branch_prefix']}/<name>`\n  Acceptance: {d['question']}\n  Test: `{d['test_command']}`" for d in config['directions'])
    project_text = section(project.get('description'), 'Concurrent directions\n\n' + directions)
    cli('project', 'update', project['id'], '--description', project_text)
    root_text = section(root.get('description'),
                        'MAIN drafts and delegates features. '
                        'Developer implements and owns approved integration; Reviewer only returns a verdict.\n\n' + directions + '\n\n' + entry_command(name))
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
        for obsolete in (target / 'roles').glob('*-debug.md'):
            obsolete.unlink()
    command = shlex.join(['python3', str(destination / name / 'wrapper.py')])
    return {'root_issue_id': root['id'], 'developer_id': developer, 'reviewer_id': reviewer,
            'command': command, 'inputs': 'propose --name SHORT-NAME --request REQUEST --direction NAME --scope SCOPE --question QUESTION [--title TITLE] [--github-issue URL]'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True, help='Ignored JSON answers and owned IDs; updated after successful writes')
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config.exists() else {}
    try:
        result = execute(config, args.config)
    except NeedsAnswer as missing:
        write_json(args.config, config)
        result = {'status': 'needs_input', 'field': missing.field, 'question': missing.question}
    print(json.dumps(result, indent=2))
