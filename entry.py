#!/usr/bin/env python3
"""Run the installed package from the issue's repository checkout."""
from pathlib import Path
import subprocess
import sys

from common import repo_root

raise SystemExit(subprocess.call([sys.executable, str(Path(__file__).with_name('wrapper.py')),
                                 *sys.argv[1:]], cwd=repo_root()))
