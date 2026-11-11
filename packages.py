"""Compile standalone packages from repository-owned procedures and runtime."""
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from common import cli

ROOT = Path(__file__).resolve().parent
RUNTIME = ('wrapper.py', 'sop.py', 'monitor.py', 'config.json', 'common.py')


def build(role, destination, *, name=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for filename in RUNTIME:
        if filename == 'config.json' and (destination / filename).exists():
            continue
        shutil.copyfile(ROOT / filename, destination / filename)
    if role == 'delegation':
        for filename in ('controller.py', 'SKILL.md', 'github_issue.py'):
            shutil.copyfile(ROOT / filename, destination / filename)
    elif role == 'installation':
        shutil.copyfile(ROOT / 'roles/installation.py', destination / 'controller.py')
        shutil.copyfile(ROOT / 'roles/installation.md', destination / 'SKILL.md')
    else:
        if role != 'feature':
            raise ValueError('Build delegation or feature.')
        shutil.copyfile(ROOT / 'roles/feature.py', destination / 'controller.py')
        shutil.copyfile(ROOT / 'roles/feature.md', destination / 'SKILL.md')
    for filename in ('DEBUG.md', 'entry.py', 'commit_report.py', 'installation.json'):
        (destination / filename).unlink(missing_ok=True)
    if role == 'feature':
        (destination / 'github_issue.py').unlink(missing_ok=True)
    for obsolete in (destination / 'roles').glob('*-debug.md'):
        obsolete.unlink()
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
