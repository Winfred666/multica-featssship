import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
MULTICA = shutil.which('multica')
sys.path.insert(0, str(ROOT / 'installation'))
from featssship import CONFIG_KEY, comment, config_ref, feature_branch


class DeliveryRoutingTests(unittest.TestCase):
    def test_blocked_recipient_is_not_a_successful_handoff(self):
        for status in ('queued', 'coalesced', 'deferred', 'steered', 'blocked'):
            response = {'id': 'posted', 'trigger_outcomes': [
                {'target_id': 'recipient', 'status': status}]}
            with self.subTest(status=status), patch('featssship.cli', side_effect=[[], response]):
                if status == 'blocked':
                    with self.assertRaisesRegex(ValueError, 'Comment posted but recipient delivery was blocked'):
                        comment('issue', 'handoff', steer_agent='recipient')
                else:
                    self.assertEqual(comment('issue', 'handoff', steer_agent='recipient'), response)

    def test_configured_short_branch_names(self):
        for prefix in ('feat/frontend', 'fix/cli'):
            self.assertEqual(feature_branch({'name': 'work', 'branch_prefix': prefix}, 'tree-horizontal-more'),
                             prefix + '/tree-horizontal-more')
        with self.assertRaisesRegex(ValueError, 'short kebab-case'):
            feature_branch({'name': 'work'}, '../another-branch')

    def test_steer_only_one_matching_supplementable_running_recipient(self):
        eligible = {'id': 'ready', 'agent_id': 'recipient', 'status': 'running', 'can_supplement': True}
        for rows, expected in (
            ([], None),
            ([{**eligible, 'can_supplement': False}], None),
            ([{k: v for k, v in eligible.items() if k != 'can_supplement'}], None),
            ([{**eligible, 'status': 'completed'}], None),
            ([{**eligible, 'agent_id': 'other'}], None),
            ([{**eligible, 'agent_id': 'other'}, eligible, {**eligible, 'id': 'second'}], 'ready'),
        ):
            with self.subTest(runs=rows), patch('featssship.cli', side_effect=[rows, {'id': 'posted'}]) as cli:
                self.assertEqual(comment('issue', 'recipient TODO', steer_agent='recipient'), {'id': 'posted'})
                self.assertEqual(cli.call_count, 2)
                words = cli.call_args.args
                self.assertEqual(words.count('--steer'), 1 if expected else 0)
                if expected:
                    self.assertEqual(words[-2:], ('--steer', expected))


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

    def installation_reply(self, content='confirm', *, author='member', parent=None):
        db = self.db()
        parent = parent or next(row['id'] for row in reversed(db['comments'])
                                if row.get('attachments'))
        row = {'id': str(uuid.uuid4()), 'issue_id': self.ids['installer'], 'parent_id': parent,
               'author_type': author, 'author_id': str(uuid.uuid4()), 'content': content}
        db['comments'].append(row)
        self.db_path.write_text(json.dumps(db))
        return row['id']

    def install(self):
        if self.installer()['status'] != 'finished':
            self.installer('edit', '--patch', '{}')
            self.installation_reply()
            self.assertEqual(self.installer('confirmed')['status'], 'finished')

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
        self.installer('edit', '--patch', '{}')
        reply = self.installation_reply()
        result = self.installer('--thread', reply, 'confirmed', ok=False)
        self.assertIn('distinct MAIN', result['error']['message'])
        self.assertEqual(len(self.db()['agents']), 1)

    def test_install_edits_complete_config_then_requires_latest_human_confirmation(self):
        seed = self.read_answers()
        db = self.db()
        del db['issues'][self.ids['installer']]['metadata'][CONFIG_KEY]
        db['issues'][self.ids['installer']]['attachments'] = []
        trigger = str(uuid.uuid4())
        db['comments'].append({'id': trigger, 'issue_id': self.ids['installer'], 'parent_id': None,
                              'author_type': 'member', 'author_id': 'human', 'content': 'Configure installation.'})
        self.db_path.write_text(json.dumps(db))
        self.assertEqual(self.installer('--thread', trigger)['status'], 'grilling')
        self.assertEqual(self.read_answers()['repository'], '')
        patch = {key: seed[key] for key in ('repository', 'directions')}
        self.installer('edit', '--patch', json.dumps(patch))
        self.assertEqual(self.read_answers()['directions'], seed['directions'])
        self.assertIn('human must reply', self.installer('confirmed', ok=False)['error']['message'])
        agent_reply = self.installation_reply(author='agent')
        self.assertIn('human must reply', self.installer('--thread', agent_reply, 'confirmed', ok=False)['error']['message'])
        old_reply = self.installation_reply()
        self.installer('--thread', old_reply, 'edit', '--patch', '{"developer":{"name":"New Developer"}}')
        self.assertIn('human must reply', self.installer('--thread', old_reply, 'confirmed', ok=False)['error']['message'])
        before_calls = len(self.db()['calls'])
        self.installer()
        self.assertEqual(self.read_answers()['developer']['name'], 'New Developer')
        self.assertFalse(any(call[:2] == ['agent', 'get'] for call in self.db()['calls'][before_calls:]))
        self.installation_reply()
        self.assertEqual(self.installer('confirmed')['status'], 'finished')
        self.assertEqual(self.db()['issues'][self.ids['installer']]['status'], 'done')

    def test_install_preserves_project_context(self):
        db = self.db()
        db['projects'][self.ids['project']]['description'] += '\nKeep this footer.'
        self.db_path.write_text(json.dumps(db))
        self.install()
        self.assertIn('Keep this footer.', self.db()['projects'][self.ids['project']]['description'])


if __name__ == '__main__':
    unittest.main()
