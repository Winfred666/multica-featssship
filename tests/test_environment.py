import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'delegation/common'))
from environment import prepare_environment


class EnvironmentTests(unittest.TestCase):
    def test_worktree_preparation_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / 'main'
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
            git('init', '-q')
            (repo / '.gitignore').write_text('node_modules/\n.env*\n!.env.example\nbackend/.venv\n')
            package = {'name': 'fixture', 'version': '1.0.0'}
            (repo / 'package.json').write_text(json.dumps(package))
            (repo / 'package-lock.json').write_text(json.dumps({**package, 'lockfileVersion': 3, 'packages': {'': package}}))
            (repo / '.env.example').write_text('PUBLIC=example')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-qm', 'fixture')
            child = Path(directory) / 'child'
            git('worktree', 'add', '-qb', 'feature', str(child))
            (repo / '.env').write_text('PRIVATE=fixture')
            (repo / 'node_modules').mkdir()
            (repo / 'node_modules/fixture').write_text('original')
            (child / 'backend').mkdir()
            (child / 'backend/.venv').symlink_to('/existing-python-env')
            prepare_environment(repo, child)
            self.assertTrue((child / 'node_modules').is_symlink())
            self.assertTrue((child / '.env').is_symlink())
            self.assertFalse((child / '.env.example').is_symlink())
            self.assertTrue((child / 'backend/.venv').is_symlink())
            (repo / 'node_modules/fixture').write_text('MAIN updated')
            self.assertEqual((child / 'node_modules/fixture').read_text(), 'original')
            (child / '.env.local').write_text('branch-specific')
            (repo / '.env.local').write_text('main-specific')
            prepare_environment(repo, child)
            self.assertEqual((child / '.env.local').read_text(), 'branch-specific')
            second = Path(directory) / 'second'
            git('worktree', 'add', '-qb', 'second', str(second))
            prepare_environment(repo, second)
            self.assertEqual((child / 'node_modules').resolve(), (second / 'node_modules').resolve())
            (child / 'node_modules').unlink()
            (child / 'package-lock.json').write_text((child / 'package-lock.json').read_text() + '\n')
            import environment
            real_run = environment.subprocess.run
            with patch('environment.subprocess.run', wraps=real_run) as run:
                prepare_environment(repo, child)
                self.assertTrue(any(call.args[0] == ['npm', 'ci', '--include=dev'] for call in run.call_args_list))
            self.assertFalse((child / 'node_modules').is_symlink())
            self.assertEqual((second / 'node_modules/fixture').read_text(), 'original')
            (child / 'node_modules').mkdir(exist_ok=True)
            (child / 'node_modules/own').write_text('retained')
            prepare_environment(repo, child)
            self.assertEqual((child / 'node_modules/own').read_text(), 'retained')
            self.assertEqual(git('status', '--porcelain'), '')
