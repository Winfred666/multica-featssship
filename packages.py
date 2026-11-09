"""Compile standalone packages from repository-owned procedures and runtime."""
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from common import cli, write_json

ROOT = Path(__file__).resolve().parent
RUNTIME = ('wrapper.py', 'sop.py', 'monitor.py', 'config.json', 'common.py', 'commit_report.py', 'entry.py', 'packages.py')


def build(role, destination, *, name=None, binding=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for filename in RUNTIME:
        shutil.copyfile(ROOT / filename, destination / filename)
    if role == 'delegation':
        for filename in ('controller.py', 'SKILL.md', 'DEBUG.md'):
            shutil.copyfile(ROOT / filename, destination / filename)
        shutil.copytree(ROOT / 'roles', destination / 'roles', dirs_exist_ok=True)
        write_json(destination / 'installation.json', binding)
    else:
        shutil.copyfile(ROOT / 'roles' / (role + '.py'), destination / 'controller.py')
        shutil.copyfile(ROOT / 'roles' / (role + '.md'), destination / 'SKILL.md')
        shutil.copyfile(ROOT / 'roles' / (role + '-debug.md'), destination / 'DEBUG.md')
        # Developer compiles reviews using these same owned sources.
        shutil.copytree(ROOT / 'roles', destination / 'roles', dirs_exist_ok=True)
        if binding:
            write_json(destination / 'review.json', binding)
    if name:
        path = destination / 'SKILL.md'
        lines = path.read_text().splitlines()
        path.write_text('\n'.join('name: ' + name if line.startswith('name:') else line for line in lines) + '\n')
    subprocess.run([sys.executable, str(destination / 'wrapper.py'), '--validate'], check=True, capture_output=True)
    return destination


def install(package, existing_id=None):
    archive = package.with_suffix('.skill')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
        for path in package.rglob('*'):
            if path.is_file() and not any(part in ('.state', '__pycache__', '.errors') for part in path.relative_to(package).parts):
                stream.write(path, path.relative_to(package))
    result = cli('skill', 'import', '--file', str(archive), '--on-conflict', 'overwrite' if existing_id else 'fail')
    if result['status'] not in ('created', 'updated'):
        raise ValueError('Skill import did not complete: ' + str(result))
    skill_id = result['skill']['id']
    if existing_id and existing_id != skill_id:
        raise ValueError('Import replaced an unexpected skill identity.')
    return skill_id


def bind(agent_id, skill_id):
    present = cli('agent', 'skills', 'list', agent_id)
    if not any(row.get('id', row.get('skill_id')) == skill_id for row in present):
        cli('agent', 'skills', 'add', agent_id, '--skill-ids', skill_id)
    present = cli('agent', 'skills', 'list', agent_id)
    if not any(row.get('id', row.get('skill_id')) == skill_id for row in present):
        raise ValueError('The imported skill is not bound to its target agent.')


def compile_review(binding, commit=None, submission_id=None):
    binding = {**binding, 'commit': commit, 'submission_id': submission_id}
    name = 'multica-featssship-review-' + binding['issue_id']
    local = Path.cwd() / '.multica' / 'featssship' / name
    receipt = local.parent / (name + '.json')
    import json
    owned = json.loads(receipt.read_text()) if receipt.exists() else {}
    package = build('reviewer', local, name=name, binding=binding)
    skill_id = install(package, binding.get('reviewer_skill_id') or owned.get('skill_id'))
    write_json(receipt, {'skill_id': skill_id})
    bind(binding['reviewer_id'], skill_id)
    return name, skill_id
