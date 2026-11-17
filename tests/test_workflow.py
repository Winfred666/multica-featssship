import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MULTICA = shutil.which('multica')
sys.path.insert(0, str(ROOT / 'installation'))
from featssship import CONFIG_KEY, config_ref, feature_branch


class BranchNamingTests(unittest.TestCase):
    def test_configured_short_branch_names(self):
        for prefix in ('feat/frontend', 'fix/cli'):
            self.assertEqual(feature_branch({'name': 'work', 'branch_prefix': prefix}, 'tree-horizontal-more'),
                             prefix + '/tree-horizontal-more')
        with self.assertRaisesRegex(ValueError, 'short kebab-case'):
            feature_branch({'name': 'work'}, '../another-branch')


class WorkflowFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='featssship-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / 'target'
        self.remote = self.base / 'origin.git'
        self.env = {**os.environ, 'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.test',
                    'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.test'}
        # Keep runtime error reporting and fixture CLI calls entirely local.
        self.env.pop('SYMBOLIC_SOP_ERROR_REPO', None)
        self.env.pop('MULTICA_TASK_ID', None)
        for key in ('MULTICA_SERVER_URL', 'MULTICA_TOKEN'):
            self.env.pop(key, None)
        self.call('git', 'init', '--bare', '--initial-branch=main', str(self.remote), cwd=self.base)
        self.call('git', 'clone', str(self.remote), str(self.repo), cwd=self.base)
        (self.repo / 'message.txt').write_text('baseline\n')
        self.commit('baseline')
        self.call('git', 'push', 'origin', 'main')
        self.ids = {name: str(uuid.uuid4()) for name in ('workspace', 'project', 'main', 'runtime', 'installer')}
        self.db_path = self.base / 'native.json'
        db = {'workspace_id': self.ids['workspace'], 'calls': [], 'agents': {
            self.ids['main']: {'id': self.ids['main'], 'runtime_id': self.ids['runtime'], 'workspace_id': self.ids['workspace'],
                               'model': 'fixture', 'thinking_level': 'high'}},
            'projects': {self.ids['project']: {'id': self.ids['project'],
            'workspace_id': self.ids['workspace'], 'description': 'Existing project context.'}},
            'issues': {}, 'comments': []}
        db['issues'][self.ids['installer']] = {'id': self.ids['installer'], 'workspace_id': self.ids['workspace'],
            'project_id': self.ids['project'], 'title': 'Install shipping', 'description': '',
            'assignee_id': self.ids['main'], 'assignee_type': 'agent', 'status': 'in_progress', 'labels': [], 'metadata': {}}
        self.db_path.write_text(json.dumps(db))
        binaries = self.base / 'bin'
        binaries.mkdir()
        script = binaries / 'multica'
        script.write_text('#!' + sys.executable + '\nimport os, runpy, sys\nif sys.argv[1:2] == [\"sop\"]: os.execv(' + repr(MULTICA) + ', [' + repr(MULTICA) + ', *sys.argv[1:]])\nrunpy.run_path(' + repr(str(ROOT / 'tests/fake_multica.py')) + ", run_name='__main__')\n")
        script.chmod(0o755)
        self.env.update(PATH=str(binaries) + os.pathsep + os.environ['PATH'], FEATSSSHIP_FAKE_DB=str(self.db_path))
        config = {'repository': str(self.remote), 'delegator': {'name': 'Delegator', 'runtime_id': self.ids['runtime'], 'model': 'fixture', 'thinking_level': 'high'}, 'developer': {'name': 'Developer', 'runtime_id': self.ids['runtime'], 'model': 'fixture'},
                  'reviewer': {'name': 'Reviewer', 'runtime_id': self.ids['runtime'], 'model': 'fixture'},
                  'directions': [{'name': 'message', 'branch_prefix': 'feat/messages', 'scope': 'message.txt', 'questions': ['Does message.txt say shipped?'],
                                  'test_command': 'python3 -c "from pathlib import Path; assert Path(\'message.txt\').exists()"'}]}
        self.write_answers(config)

    def call(self, *words, cwd=None, env=None, ok=True):
        process = subprocess.run(words, cwd=cwd or self.repo, env=env or self.env, text=True, capture_output=True, input='')
        if ok:
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        return process

    def commit(self, message):
        self.call('git', 'add', 'message.txt')
        self.call('git', 'commit', '-m', message)

    def db(self):
        return json.loads(self.db_path.read_text())

    def document(self, issue, key=CONFIG_KEY):
        reference = config_ref(issue, key)
        if not reference:
            return {}
        if reference.get('attachment_id'):
            return json.loads(self.db()['attachments'][reference['attachment_id']]['data'])
        owner = self.db()['issues'][reference['issue_id']]
        return json.loads(next(row['data'] for row in reversed(owner['attachments']) if row['filename'] == reference['filename']))

    def read_answers(self):
        return self.document(self.db()['issues'][self.ids['installer']])

    def write_answers(self, config):
        db = self.db()
        owner = db['issues'][self.ids['installer']]
        reference = {'issue_id': owner['id'], 'filename': 'featssship-config.json'}
        owner['metadata'][CONFIG_KEY] = json.dumps(reference)
        attachment = {'id': str(uuid.uuid4()), 'filename': reference['filename'], 'data': json.dumps(config),
                      'created_at': str(len(db.setdefault('attachments', {}))).zfill(10)}
        db['attachments'][attachment['id']] = attachment
        owner.setdefault('attachments', []).append(attachment)
        self.db_path.write_text(json.dumps(db))

    def installer(self, *args, ok=True):
        env = {**self.env, 'MULTICA_ISSUE_ID': self.ids['installer'],
               'MULTICA_AGENT_ID': self.ids['main'], 'MULTICA_WORKSPACE_ID': self.ids['workspace'],
               'MULTICA_SOP_SKILL_ROOTS': str(getattr(self, 'installer_package', ROOT / 'installation').parent)}
        result = self.call(MULTICA, 'sop', 'run', 'multica-featssship-installation', *args, env=env, ok=ok)
        return json.loads(result.stdout)

    def install(self):
        if self.installer()['status'] != 'finished':
            self.installer('publish', '--patch', '{}')
            self.assertEqual(self.installer('confirm')['status'], 'finished')

    def test_standalone_bundles_and_packaged_installer(self):
        from packages import build
        env = {**self.env, 'MULTICA_ISSUE_ID': self.ids['installer'],
               'MULTICA_WORKSPACE_ID': self.ids['workspace']}
        for role in ('installation', 'delegation', 'feature'):
            directory = build(role, self.base / (role + '-package'))
            self.assertEqual(json.loads(self.call(MULTICA, 'sop', 'dev', 'validate', str(directory), env=env).stdout)['status'], 'valid')
            env['MULTICA_SOP_SKILL_ROOTS'] = str(directory.parent)
            name = next(line[6:] for line in (directory / 'SKILL.md').read_text().splitlines() if line.startswith('name: '))
            help_text = self.call(MULTICA, 'sop', 'run', name, '--help', env=env).stdout
            self.assertEqual(help_text.strip(), (directory / 'SKILL.md').read_text().split('---', 2)[2].strip())
            package = self.base / (role + '-package')
            (package / 'config.json').write_text('{"DEBUG": false}\n')
            build(role, package)
            self.assertFalse(json.loads((package / 'config.json').read_text())['DEBUG'])
        # Installation must work without importing from the featssship checkout.
        self.installer_package = self.base / 'installation-package'
        self.install()

    def test_install_rejects_self_review(self):
        config = self.read_answers()
        config['developer']['id'] = config['reviewer']['id'] = self.ids['main']
        self.write_answers(config)
        self.installer()
        self.installer('publish', '--patch', '{}')
        result = self.installer('confirm', ok=False)
        self.assertIn('distinct MAIN', result['error']['message'])
        self.assertEqual(len(self.db()['agents']), 1)

    def test_install_preserves_project_context(self):
        db = self.db()
        db['projects'][self.ids['project']]['description'] += '\nKeep this footer.'
        self.db_path.write_text(json.dumps(db))
        self.install()
        self.assertIn('Keep this footer.', self.db()['projects'][self.ids['project']]['description'])

    def test_confirmation_renews_one_config_and_retries_with_resolved_roles(self):
        # Real installer/helpers and Git; platform commands use fake_multica.py.
        import install
        from featssship import read_config, write_config
        issue = self.db()['issues'][self.ids['installer']]
        config = self.read_answers()
        config['manual'] = True
        state, snapshots = {}, []
        def checkpoint(reference, document):
            row = write_config(reference, document)
            snapshots.append(read_config(reference))
            return row
        env = {**self.env, 'MULTICA_ISSUE_ID': issue['id']}
        previous = Path.cwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, previous)
        with patch.dict(os.environ, env), patch.object(install, 'write_config', side_effect=checkpoint):
            with patch.object(install, 'deploy', side_effect=ValueError('deployment interrupted')):
                with self.assertRaisesRegex(ValueError, 'deployment interrupted'):
                    install.execute(config, issue, state, lambda: None)
            reference = config_ref(self.db()['issues'][issue['id']])
            resolved = read_config(reference)
            result = install.execute(resolved, issue, state, lambda: None)
            # Recover after a lost reference save, without renewing a legacy file.
            recovered = {key: value for key, value in reference.items() if key != 'attachment_id'}
            write_config(recovered, resolved)
        keys = ['installed_' + role + '_id' for role in ('delegator', 'developer', 'reviewer')]
        self.assertEqual([[key for key in keys if key in snapshot] for snapshot in snapshots],
                         [keys[:1], keys[:2], keys])
        self.assertEqual(result['root_issue_id'], state['main_issue_id'])
        self.assertEqual(result['developer_id'], resolved[keys[1]])
        self.assertEqual(result['reviewer_id'], resolved[keys[2]])
        self.assertEqual(recovered, reference)
        db = self.db()
        self.assertEqual(len(db['agents']), 4)  # installer plus three created roles
        self.assertEqual(len(db['issues']), 2)  # installer plus one retained MAIN
        independent = [row for row in db['attachments'].values() if 'issue_id' in row]
        self.assertEqual([row['id'] for row in independent], [reference['attachment_id']])
        self.assertIsNone(independent[0]['issue_id'])
        self.assertIsNone(independent[0]['comment_id'])
        self.assertTrue(json.loads(independent[0]['data'])['manual'])
        self.assertEqual(config_ref(db['issues'][state['main_issue_id']]), reference)
        self.assertFalse(db['comments'])
        self.assertEqual(len(db['issues'][issue['id']]['attachments']), 1)  # legacy file untouched


if __name__ == '__main__':
    unittest.main()
