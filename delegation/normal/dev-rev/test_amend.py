"""Exercise concurrent amendment publication with real Git repositories."""
import ast
import json
from types import SimpleNamespace
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'installation'))
from featssship import git, run

source = Path(__file__).with_name('controller.py').read_text()
names = ('retained_rebase', 'parent_worktrees', 'advance_parent', 'push', 'recover',
         'diff_report', 'feature_link', 'final_note')
functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names]
sop = {'Path': Path, 'git': git, 'run': run, 'sys': sys, 'json': json}
exec(compile(ast.Module(body=functions, type_ignores=[]), 'controller.py', 'exec'), sop)


class AmendmentTest(unittest.TestCase):
    def test_concurrent_amendments(self):
        for conflict in (False, True):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                env = {'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.com',
                       'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.com', 'GIT_EDITOR': 'true'}
                def call(repo, *args):
                    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                          text=True, capture_output=True).stdout.strip()
                def edit(repo, name, content):
                    (repo / name).write_text(content + '\n')
                    call(repo, 'add', name)
                with patch.dict(os.environ, env):
                    call(root, 'init', '--bare', '--initial-branch=main', 'origin.git')
                    call(root, 'clone', str(root / 'origin.git'), 'main')
                    main, feature, other = root / 'main', root / 'feature', root / 'other'
                    edit(main, 'seed', 'seed')
                    call(main, 'commit', '-m', 'base')
                    for name in ('a', 'b', 'local'):
                        edit(main, name, 'original')
                    call(main, 'commit', '-m', 'feature')
                    call(main, 'push', 'origin', 'main')
                    base = call(main, 'rev-parse', 'HEAD')
                    call(main, 'worktree', 'add', '-b', 'amend', str(feature), base)
                    edit(feature, 'b', 'incoming')
                    call(feature, 'commit', '--amend', '--no-edit')
                    call(root, 'clone', str(root / 'origin.git'), 'other')
                    edit(other, 'b' if conflict else 'a', 'upstream')
                    call(other, 'commit', '--amend', '--no-edit')
                    call(other, 'push', '--force-with-lease=refs/heads/main:' + base, 'origin', 'main')
                    (main / 'local').write_text('main edit\n')
                    moved = []
                    def racing_git(repo, *args):
                        if args[0] == 'push' and not conflict and not moved:
                            moved.append(args)
                            edit(other, 'newer', 'newer work')
                            call(other, 'commit', '-m', 'newer work')
                            call(other, 'push', 'origin', 'main')
                        return git(repo, *args)
                    sop.update(git=racing_git, check_repo=lambda *a: None, shared_repo=lambda c: Path.cwd(),
                               test=lambda *a: None, wake_recovery=lambda c: {'phase': 'integration_error'},
                               finish=lambda c, commit, published: {'commit': commit, 'note': sop['final_note'](c)})
                    context = {'phase': 'amending', 'binding': {'parent_branch': 'main', 'test_command': 'true',
                               'repository': str(root / 'origin.git')}, 'state': {'integrated': base}}
                    old_cwd = Path.cwd()
                    try:
                        os.chdir(feature)
                        result = sop['push'](SimpleNamespace(changes=json.dumps({'b': 'Updates the delivered value.'})), context)
                        if conflict:
                            self.assertEqual(result['phase'], 'integration_error')
                            self.assertIsNotNone(sop['retained_rebase'](feature))
                            edit(feature, 'b', 'resolved')
                            context['phase'] = 'integration_error'
                            result = sop['recover'](None, context)
                    finally:
                        os.chdir(old_cwd)
                        sop['git'] = git
                    commit = result['commit']
                    self.assertEqual(call(main, 'show', 'origin/main:b'), 'resolved' if conflict else 'incoming')
                    self.assertEqual(call(main, 'show', 'origin/main:a'), 'original' if conflict else 'upstream')
                    self.assertEqual(call(main, 'show', 'origin/main:local'), 'original')
                    self.assertEqual((main / 'local').read_text(), 'main edit\n')
                    self.assertEqual(call(main, 'rev-parse', 'main'), commit)
                    self.assertIn('/commit/' + commit, result['note'])
                    self.assertIn('compare/' + call(main, 'rev-parse', 'origin/main^') + '...' + commit, result['note'])
                    self.assertIn('| `b` | +1 / -1 | Updates the delivered value. |', result['note'])
                    if not conflict:
                        self.assertTrue(moved[0][1].startswith('--force-with-lease=refs/heads/main:'))
                        self.assertEqual(call(main, 'show', 'origin/main:newer'), 'newer work')
                        edit(feature, 'local', 'published edit')
                        call(feature, 'commit', '-m', 'conflicting update')
                        warning = sop['advance_parent'](feature, context['binding'], call(feature, 'rev-parse', 'HEAD'), commit)
                        self.assertIn('stash', warning)
                        self.assertEqual(call(main, 'show', 'stash@{0}:local'), 'main edit')
                        self.assertEqual((feature / 'local').read_text(), 'published edit\n')
        self.assertIn("('push', 'merge_result')", source)


if __name__ == '__main__':
    unittest.main()
