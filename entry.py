#!/usr/bin/env python3
"""Materialize a bound package in this checkout's ignored local skill area."""
from pathlib import Path
import shutil
import subprocess
import sys

from common import exclude_local, repo_root

source = Path(__file__).resolve().parent
name = next(line.split(':', 1)[1].strip() for line in (source / 'SKILL.md').read_text().splitlines() if line.startswith('name:'))
repo = repo_root()
exclude_local(repo)
target = repo / '.agents' / 'skills' / name
if target != source:
    shutil.copytree(source, target, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('.state', '.errors', '__pycache__', '.git', '.multica', '.agents'))
raise SystemExit(subprocess.call([sys.executable, str(target / 'wrapper.py'), *sys.argv[1:]], cwd=repo))
