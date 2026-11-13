"""Compile standalone packages from repository-owned procedures."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
# Source checkout: sibling bundle. Standalone installer: bundled child.
DELEGATION = ROOT / 'delegation' if (ROOT / 'delegation').is_dir() else ROOT.parent / 'delegation'
SOURCES = {'installation': ROOT, 'delegation': DELEGATION, 'feature': DELEGATION / 'dev-rev'}
ENGINE_FILES = ('wrapper.py', 'sop.py', 'monitor.py', 'common.py')


def build(role, destination, *, name=None):
    if role not in SOURCES:
        raise ValueError('Build installation, delegation or feature.')
    source = SOURCES[role]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ('config.json', 'featssship.py'):
        if filename == 'config.json' and (destination / filename).exists():
            continue
        shutil.copyfile(ROOT / filename, destination / filename)
    for filename in ('controller.py', 'SKILL.md'):
        shutil.copyfile(source / filename, destination / filename)
    if role == 'delegation':
        shutil.copyfile(source / 'github_issue.py', destination / 'github_issue.py')
    elif role == 'installation':
        for filename in ('install.py', 'packages.py'):
            shutil.copyfile(source / filename, destination / filename)
        build('delegation', destination / 'delegation')
        build('feature', destination / 'delegation/dev-rev')
    for filename in (*ENGINE_FILES, 'DEBUG.md', 'entry.py', 'commit_report.py', 'installation.json'):
        (destination / filename).unlink(missing_ok=True)
    if role == 'feature':
        (destination / 'github_issue.py').unlink(missing_ok=True)
    for obsolete in (destination / 'roles').glob('*-debug.md'):
        obsolete.unlink()
    if name:
        path = destination / 'SKILL.md'
        lines = path.read_text().splitlines()
        original = next(line[6:] for line in lines if line.startswith('name: '))
        path.write_text('\n'.join('name: ' + name if line.startswith('name:') else line for line in lines).replace(
            'multica sop run ' + original, 'multica sop run ' + name) + '\n')
    subprocess.run(['multica', 'sop', 'dev', 'validate', str(destination)], check=True, capture_output=True)
    return destination
