"""Prepare ignored local npm and environment inputs before starting a child."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def ignored(repo, path):
    return subprocess.run(['git', '-C', str(repo), 'check-ignore', '-q', '--', str(path)]).returncode == 0


def present(path):
    return path.exists() or path.is_symlink()


def prepare_environment(repo, worktree):
    # Never replace a branch's installed environment, even a dangling link.
    for source in repo.glob('.env*'):
        target = worktree / source.name
        if source.is_file() and ignored(repo, source.name) and ignored(worktree, source.name) and not present(target):
            target.symlink_to(source.resolve())
    modules = worktree / 'node_modules'
    if present(modules) or not ignored(worktree, 'node_modules/'):
        return
    inputs = ('package.json', 'package-lock.json', '.npmrc')
    if not all((worktree / name).is_file() for name in inputs[:2]):
        return
    signature = lambda root: [(root / name).read_bytes() if (root / name).is_file() else b'' for name in inputs]
    wanted = signature(worktree)
    if wanted != signature(repo) or not (repo / 'node_modules').is_dir():
        # npm uses its normal user cache, but owns a separate branch directory.
        result = subprocess.run(['npm', 'ci', '--include=dev'], cwd=worktree, capture_output=True, text=True)
        if result.returncode:
            raise ValueError('Branch npm ci failed; repair its isolated environment and retry: ' + result.stderr)
        return
    # A snapshot, not a link to mutable MAIN: later MAIN installs cannot break children.
    key = hashlib.sha256(b'\0'.join(wanted)).hexdigest()
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    cache = common / 'featsship-envs'
    cache.mkdir(exist_ok=True)
    snapshot = cache / key
    if not snapshot.exists():
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            staged = Path(temporary) / key
            shutil.copytree(repo / 'node_modules', staged, symlinks=True)
            if signature(repo) != wanted:
                raise ValueError('MAIN dependency inputs changed during environment preparation; retry dispatch.')
            # Another dispatch may have completed the same snapshot meanwhile.
            if not snapshot.exists():
                staged.rename(snapshot)
    modules.symlink_to(snapshot, target_is_directory=True)
