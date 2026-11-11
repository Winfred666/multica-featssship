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
sys.path.insert(0, str(ROOT))
from common import INSTALLATION_KEY, PROCESS_KEY, comment, feature_branch, installation_config, process_config, unpack


class DeliveryRoutingTests(unittest.TestCase):
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
            with self.subTest(runs=rows), patch('common.cli', side_effect=[rows, {'id': 'posted'}]) as cli:
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
        self.ids = {name: str(uuid.uuid4()) for name in ('workspace', 'project', 'root', 'main', 'runtime', 'installer')}
        self.db_path = self.base / 'native.json'
        db = {'workspace_id': self.ids['workspace'], 'calls': [], 'agents': {
            self.ids['main']: {'id': self.ids['main'], 'runtime_id': self.ids['runtime'], 'workspace_id': self.ids['workspace'],
                               'model': 'fixture', 'thinking_level': 'high'}},
            'skills': {}, 'bindings': {}, 'projects': {self.ids['project']: {'id': self.ids['project'],
            'workspace_id': self.ids['workspace'], 'description': 'Existing project context.'}},
            'issues': {self.ids['root']: {'id': self.ids['root'], 'workspace_id': self.ids['workspace'],
            'project_id': self.ids['project'], 'title': 'MAIN DEV: Existing shipping root', 'description': 'Existing root context.',
            'assignee_id': self.ids['main'], 'assignee_type': 'agent', 'status': 'in_progress', 'labels': [], 'metadata': {'unrelated': 'preserve'}}}, 'comments': [],
            'github_calls': [], 'github': {'url': 'https://github.com/owner/requests/issues/42',
            'title': 'Ship the message', 'body': 'Requirement: write shipped. Verification: read message.txt.',
            'state': 'OPEN', 'comments': [], 'remote': str(self.remote)}}
        db['issues'][self.ids['installer']] = {**db['issues'][self.ids['root']],
            'id': self.ids['installer'], 'title': 'Install shipping', 'metadata': {}}
        db['issues'][self.ids['root']]['parent_issue_id'] = self.ids['installer']
        self.db_path.write_text(json.dumps(db))
        binaries = self.base / 'bin'
        binaries.mkdir()
        script = binaries / 'multica'
        script.write_text('#!' + sys.executable + '\nimport runpy\nrunpy.run_path(' + repr(str(ROOT / 'tests/fake_multica.py')) + ", run_name='__main__')\n")
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

    def commit(self, message, *, amend=False):
        self.call('git', 'add', 'message.txt')
        self.call('git', 'commit', *(['--amend'] if amend else []), '-m', message)
        return self.call('git', 'rev-parse', 'HEAD').stdout.strip()

    def db(self):
        return json.loads(self.db_path.read_text())

    def read_answers(self):
        return installation_config(self.db()['issues'][self.ids['installer']])

    def write_answers(self, config):
        db = self.db()
        db['issues'][self.ids['installer']]['metadata'][INSTALLATION_KEY] = json.dumps(config)
        self.db_path.write_text(json.dumps(db))

    def record(self, kind, issue=None):
        for row in reversed(self.db()['comments']):
            if row['issue_id'] == (issue or self.feature_id):
                data = unpack(row['content'], kind)
                if data:
                    return data, row
        self.fail('Missing native record: ' + kind)

    def installer(self, *args, ok=True):
        env = {**self.env, 'MULTICA_ISSUE_ID': self.ids['installer'],
               'MULTICA_AGENT_ID': self.ids['main'], 'MULTICA_WORKSPACE_ID': self.ids['workspace']}
        result = self.call(sys.executable, str(ROOT / 'install.py'), *args, env=env, ok=ok)
        return json.loads(result.stdout)

    def installation_reply(self, content='confirm', *, author='member', parent=None):
        db = self.db()
        parent = parent or next(row['id'] for row in reversed(db['comments'])
                                if unpack(row['content'], 'installation-config'))
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
        audit = self.read_answers()
        root = next(row for row in self.db()['issues'].values() if row.get('parent_issue_id') == self.ids['installer'] and row['title'].startswith('MAIN DEV:'))
        self.ids['root'] = root['id']
        self.config = {**audit, 'root_issue_id': root['id'],
                       **{key: audit['installed_' + key] for key in ('delegator_id', 'developer_id', 'reviewer_id', 'feature_skill_id', 'delegation_skill_id')}}
        self.root_package = self.repo / '.agents/skills' / ('multica-featssship-' + self.ids['project'][:8])
        self.developer = self.repo / '.agents/skills/multica-featssship-develop-review'
        from packages import build
        self.reviewer = build('feature', self.base / 'reviewer-skill')
        return self.config

    def invoke(self, package, *args, role='developer', issue=None, task=None, trigger=None, ok=True, plain=False):
        self.task = task or str(uuid.uuid4())
        env = {**self.env, 'MULTICA_AGENT_ID': self.config[role + '_id'],
               'MULTICA_ISSUE_ID': issue or self.feature_id, 'MULTICA_WORKSPACE_ID': self.ids['workspace']}
        if trigger:
            env['FEATSSSHIP_TRIGGER'] = trigger
        result = self.call(sys.executable, str(package / 'wrapper.py'), *args, env=env, ok=ok)
        if plain:
            return result
        output = json.loads(result.stdout)
        self.assertNotIn('data', output, output)
        if ok:
            self.assertNotIn('error', output, output)
        return output

    def propose(self, *, github=False, mirror=False, question='Does message.txt say shipped?'):
        task = str(uuid.uuid4())
        self.invoke(self.root_package, role='delegator', issue=self.ids['root'], task=task)
        title = 'Message: ship requested text'
        if mirror:
            title = '[' + title + '](' + self.db()['github']['url'] + ')'
        options = ['--title', title] if mirror else []
        if github:
            options += ['--github-issue', self.db()['github']['url']]
        output = self.invoke(self.root_package, 'propose', '--name', 'ship-message', '--request', 'Write shipped in message.txt.',
                             '--direction', 'message', '--scope', 'message.txt', '--question', question,
                             *options, role='delegator', issue=self.ids['root'], task=task)
        self.spec_id = self.record('spec', self.ids['root'])[1]['id']
        return task

    def ask_and_reply(self, question, answer):
        db = self.db()
        asked = {'id': str(uuid.uuid4()), 'issue_id': self.ids['root'], 'parent_id': self.spec_id,
                 'author_type': 'agent', 'author_id': self.ids['main'], 'content': question}
        reply = {'id': str(uuid.uuid4()), 'issue_id': self.ids['root'], 'parent_id': asked['id'],
                 'author_type': 'member', 'author_id': str(uuid.uuid4()), 'content': answer}
        db['comments'].extend((asked, reply))
        self.db_path.write_text(json.dumps(db))
        return reply['id']

    def dispatch(self, *, github=False, mirror=False, question='Does message.txt say shipped?'):
        task = self.propose(github=github, mirror=mirror, question=question)
        output = self.invoke(self.root_package, 'dispatch', role='delegator', issue=self.ids['root'], task=task)
        self.feature_id = self.record('dispatch', self.ids['root'])[0]['issue_id']
        self.binding = process_config(self.db()['issues'][self.feature_id])
        # Model the already-bound issue checkout, not worker-side branch setup.
        self.call('git', 'switch', '-c', self.binding['branch'], 'origin/main')
        return output

    def state(self, issue=None, package=None):
        package = package or self.developer
        name = next(line[6:] for line in (package / 'SKILL.md').read_text().splitlines() if line.startswith('name: '))
        value = self.db()['issues'][issue or self.feature_id]['metadata'].get('sop.' + name)
        return json.loads(value) if value else {}

    def submit(self, text):
        self.invoke(self.developer)
        (self.repo / 'message.txt').write_text(text + '\n')
        commit = self.commit(text, amend=bool(self.state().get('commit')))
        before = len(self.db()['comments'])
        result = self.invoke(self.developer, 'submit', '--summary', 'Updated message.txt: ' + text, plain=True)
        self.assertEqual(result.stdout, 'Delivery/review/work done this round, exit directly and silently\n')
        self.assertEqual(result.stderr, '')
        self.assert_delivery(before, self.config['reviewer_id'], self.feature_id)
        return commit

    def review(self, verdict):
        self.invoke(self.reviewer, role='reviewer')
        before = len(self.db()['comments'])
        result = self.invoke(self.reviewer, verdict, '--finding',
                           'Acceptance, necessary additions and scope verified.' if verdict == 'approve' else
                           'Replace almost with shipped.', role='reviewer', plain=True)
        self.assertEqual(result.stdout, 'Delivery/review/work done this round, exit directly and silently\n')
        self.assertEqual(result.stderr, '')
        self.assert_delivery(before, self.config['developer_id'], self.feature_id)
        return self.state()['output']

    def integrate(self):
        self.invoke(self.developer)
        before = len(self.db()['comments'])
        result = self.invoke(self.developer, 'integrate', plain=True)
        self.assertEqual(result.stdout, 'Delivery/review/work done this round, exit directly and silently\n')
        self.assertEqual(result.stderr, '')
        self.assertEqual(self.state(), {})
        self.assert_delivery(before, self.config['delegator_id'], self.ids['root'])

    def assert_delivery(self, before, recipient, issue):
        rows = self.db()['comments'][before:]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['issue_id'], issue)
        body = rows[0]['content']
        self.assertIn('mention://agent/' + recipient, body)
        self.assertEqual(body.count('mention://agent/'), 1)
        self.assertEqual(body.count('TODO:'), 1)
        self.assertIn('mention://issue/' + self.feature_id, body)

    def parent_notes(self):
        return [r['content'] for r in self.db()['comments']
                if r['issue_id'] == self.ids['root'] and '[Feature]' in r['content']]

    def advance_main(self, filename, content):
        other = self.base / 'other'
        self.call('git', 'clone', str(self.remote), str(other), cwd=self.base)
        (other / filename).write_text(content)
        self.call('git', 'add', filename, cwd=other)
        self.call('git', 'commit', '-m', 'Concurrent change', cwd=other)
        self.call('git', 'push', 'origin', 'main', cwd=other)

    def test_two_agent_correction_merge_and_minimal_binding(self):
        self.install()
        for package in (self.root_package, self.developer, self.reviewer):
            self.assertIs(json.loads((package / 'config.json').read_text())['DEBUG'], True)
        first = self.db()
        self.install()
        self.assertEqual(set(self.db()['agents']), set(first['agents']))
        self.assertEqual(set(self.db()['skills']), set(first['skills']))
        self.assertEqual(len(first['skills']), 2)
        self.dispatch()
        self.assertEqual(set(self.binding), {'questions', 'branch', 'parent_branch'})
        self.assertEqual(self.binding['branch'], 'feat/messages/ship-message')
        self.assertEqual(self.call('git', 'ls-remote', '--heads', 'origin', 'featssship/*').stdout, '')
        for role in ('developer', 'reviewer'):
            self.assertIn(self.config['feature_skill_id'], self.db()['bindings'][self.config[role + '_id']])
        initial = self.invoke(self.developer)
        self.assertEqual(initial['status'], 'develop')
        self.assertEqual(len(initial['next_step']), 2)  # submit and quit, not prepare.
        before = self.state()
        for event in ('init', 'quit'):
            denied = self.invoke(self.reviewer, *([] if event == 'init' else [event]), role='reviewer', ok=False, plain=True)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(denied.stdout, '')
            self.assertIn('belongs to developer', denied.stderr)
            self.assertEqual(self.state(), before)
        first_commit = self.submit('almost')
        self.assertNotIn('branch', self.state())  # MAIN's binding is the single source of the name.
        before = self.state()
        for event in ('init', 'approve', 'rework'):
            denied = self.invoke(self.developer, *([] if event == 'init' else [event]), ok=False, plain=True)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(denied.stdout, '')
            self.assertIn('belongs to reviewer', denied.stderr)
            self.assertEqual(self.state(), before)
        self.assertEqual(self.review('rework')['status'], 'develop')
        commit = self.submit('shipped')
        self.assertNotEqual(first_commit, commit)
        self.advance_main('other.txt', 'Concurrent safe change\n')
        self.assertEqual(self.review('approve')['status'], 'integrate')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'baseline\n')
        self.assertEqual(self.parent_notes(), [])
        self.integrate()
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'shipped\n')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:other.txt').stdout, 'Concurrent safe change\n')
        self.assertEqual(len(self.parent_notes()), 1)
        self.assertIn('Merged ', self.parent_notes()[0])
        self.assertEqual(self.state(), {})
        self.assertNotIn('sop.' + self.root_package.name, self.db()['issues'][self.ids['root']]['metadata'])
        self.assertEqual(self.db()['issues'][self.ids['root']]['metadata']['unrelated'], 'preserve')
        self.assertEqual(len(self.call('git', 'worktree', 'list', '--porcelain').stdout.split('worktree ')), 2)
        self.assertEqual(self.call('git', 'branch', '--show-current').stdout.strip(), self.binding['branch'])
        self.assertLessEqual(self.db()['peak_metadata_bytes'], 8192)
        self.assertEqual(self.invoke(self.developer, plain=True).stdout,
                         'Delivery/review/work done this round, exit directly and silently\n')
        self.assertEqual(len(self.parent_notes()), 1)

    def test_manual_check_reports_to_parent_and_finishes(self):
        db = self.db()
        db['issues'][self.ids['root']]['labels'] = [{'id': 'manual-label', 'name': 'manual'}]
        self.db_path.write_text(json.dumps(db))
        self.install(); self.dispatch(); self.submit('shipped')
        self.assertEqual(self.db()['issues'][self.feature_id]['labels'], [{'id': 'manual-label', 'name': 'manual'}])
        self.assertEqual(self.review('approve')['status'], 'integrate')
        self.integrate()
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'baseline\n')
        self.assertIn('Manual check required', self.parent_notes()[0])
        self.assertEqual(self.state(), {})

    def test_main_named_branch_guards_and_competing_first_push(self):
        self.install(); self.dispatch()
        self.invoke(self.developer)
        (self.repo / 'message.txt').write_text('shipped\n')
        self.commit('shipped')
        self.call('git', 'switch', 'main')
        denied = self.invoke(self.developer, 'submit', '--summary', 'wrong branch', plain=True, ok=False)
        self.assertIn('one feature branch selected by MAIN', denied.stdout)
        self.call('git', 'switch', self.binding['branch'])
        self.call('git', 'checkout', '--detach', 'HEAD')
        denied = self.invoke(self.developer, 'submit', '--summary', 'detached', plain=True, ok=False)
        self.assertIn('one feature branch selected by MAIN', denied.stdout)
        self.call('git', 'switch', self.binding['branch'])
        self.call('git', 'remote', 'set-url', 'origin', str(self.base / 'wrong.git'))
        denied = self.invoke(self.developer, 'submit', '--summary', 'wrong repository', plain=True, ok=False)
        self.assertIn('configured target repository', denied.stdout)
        self.call('git', 'remote', 'set-url', 'origin', str(self.remote))
        # Another issue claimed the short name before submission: do not overwrite it.
        self.call('git', 'push', 'origin', 'main:refs/heads/' + self.binding['branch'])
        denied = self.invoke(self.developer, 'submit', '--summary', 'name collision', plain=True, ok=False)
        self.assertIn('stale info', denied.stdout)
        self.assertEqual(self.call('git', 'ls-remote', 'origin', self.binding['branch']).stdout.split()[0],
                         self.call('git', 'rev-parse', 'main').stdout.strip())
        self.call('git', 'push', 'origin', ':refs/heads/' + self.binding['branch'])
        self.invoke(self.developer, 'submit', '--summary', 'shipped', plain=True)
        self.call('git', 'switch', '-c', 'other-feature')
        denied = self.invoke(self.reviewer, 'approve', '--finding', 'wrong branch', role='reviewer', plain=True, ok=False)
        self.assertIn('one feature branch selected by MAIN', denied.stdout)
        self.call('git', 'switch', self.binding['branch'])
        self.assertEqual(self.review('approve')['status'], 'integrate')

    def test_changed_revision_rejected(self):
        self.install(); self.dispatch(); self.submit('shipped')
        (self.repo / 'message.txt').write_text('unreviewed\n')
        self.commit('unreviewed', amend=True)
        before = self.state()['commit']
        rejected = self.invoke(self.reviewer, 'approve', '--finding', 'Looks fine', role='reviewer', ok=False)
        self.assertIn('exact submitted revision', rejected['error']['message'])
        self.assertEqual(self.parent_notes(), [])
        self.assertEqual(self.state()['commit'], before)

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

    def test_install_creates_own_main_child_and_reuses_it(self):
        legacy = self.read_answers()
        legacy['main'] = legacy.pop('delegator')
        self.write_answers(legacy)
        old_root = self.ids['root']
        db = self.db()
        del db['issues'][old_root]
        self.db_path.write_text(json.dumps(db))
        result = self.install()
        self.assertIn('delegator', self.read_answers())
        self.assertNotIn('main', self.read_answers())
        self.assertIn('installed_delegator_id', self.read_answers())
        self.assertNotIn('installed_main_id', self.read_answers())
        child = self.db()['issues'][result['root_issue_id']]
        self.assertNotEqual(child['id'], old_root)
        self.assertEqual(child['parent_issue_id'], self.ids['installer'])
        self.assertEqual(child['status'], 'backlog')
        self.assertTrue(child['title'].startswith('MAIN DEV:'))
        main = self.db()['agents'][self.config['delegator_id']]
        self.assertNotEqual(main['id'], self.ids['main'])
        self.assertEqual((main['runtime_id'], main['model'], main['thinking_level']),
                         (self.ids['runtime'], 'fixture', 'high'))
        self.assertIn(self.config['delegation_skill_id'], self.db()['bindings'][main['id']])
        before = self.db()
        self.assertEqual(self.install()['root_issue_id'], child['id'])
        self.assertEqual(set(self.db()['issues']), set(before['issues']))
        self.assertEqual(set(self.db()['agents']), set(before['agents']))
        # A confirmed continuation finds MAIN through children and reuses proven IDs.
        db = self.db()
        db['issues'][self.ids['installer']]['status'] = 'in_progress'
        self.db_path.write_text(json.dumps(db))
        self.assertEqual(self.install()['root_issue_id'], child['id'])
        self.assertEqual(set(self.db()['issues']), set(before['issues']))
        self.assertEqual(set(self.db()['agents']), set(before['agents']))
        self.assertFalse(any(call[:2] == ['issue', 'list'] for call in self.db()['calls']))

    def test_install_edits_complete_config_then_requires_latest_human_confirmation(self):
        seed = self.read_answers()
        self.write_answers({})
        db = self.db()
        trigger = str(uuid.uuid4())
        db['comments'].append({'id': trigger, 'issue_id': self.ids['installer'], 'parent_id': None,
                              'author_type': 'member', 'author_id': 'human', 'content': 'Configure installation.'})
        self.db_path.write_text(json.dumps(db))
        initial = self.installer('--thread', trigger)
        self.assertIn('"delegator":', initial['instruction'])
        self.assertNotIn('"main":', initial['instruction'])
        confirm_choice = initial['next_step'][1]['instruction']
        self.assertIn('human replies confirm', confirm_choice)
        self.assertNotIn('--thread', confirm_choice)
        self.assertEqual(initial['status'], 'grilling')
        self.assertIn('workflow', initial['instruction'])
        self.assertNotIn('one edit', initial['instruction'])
        self.assertNotIn('this SoP', initial['instruction'])
        self.assertIn('Current config:', initial['instruction'])
        self.assertIn('runtime/model', initial['instruction'])
        self.assertIn('"scope": "."', initial['instruction'])
        self.assertEqual([step['command'].split()[2] for step in initial['next_step']],
                         ['edit', 'confirmed', 'quit'])
        patch = {key: seed[key] for key in ('repository', 'directions')}
        edited = self.installer('edit', '--patch', json.dumps(patch))
        self.assertIn('Edit finished, exit directly and silently in this round', edited['instruction'])
        config, row = self.record('installation-config', self.ids['installer'])
        self.assertEqual(row['parent_id'], trigger)
        self.assertEqual(config['directions'], seed['directions'])
        self.assertTrue(row['content'].endswith('Edit or confirm.'))
        self.assertEqual(installation_config(self.db()['issues'][self.ids['installer']]), config)
        self.assertEqual(installation_config(self.db()['issues'][self.ids['root']]), {})
        self.assertEqual(len(self.db()['agents']), 1)
        self.assertEqual(len(self.db()['skills']), 0)
        self.assertIn('human must reply', self.installer('confirmed', ok=False)['error']['message'])
        agent_reply = self.installation_reply(author='agent')
        self.assertIn('human must reply', self.installer('--thread', agent_reply, 'confirmed', ok=False)['error']['message'])
        old_reply = self.installation_reply()
        self.installer('--thread', old_reply, 'edit', '--patch', '{"developer":{"name":"New Developer"}}')
        self.assertIn('human must reply', self.installer('--thread', old_reply, 'confirmed', ok=False)['error']['message'])
        # A different native task must retain issue-owned edits without a local answers file.
        self.assertIn('New Developer', self.installer()['instruction'])
        self.installation_reply()
        self.installation_reply('Wait, change the config first.')
        self.assertIn('human must reply', self.installer('confirmed', ok=False)['error']['message'])
        self.installation_reply()
        finished = self.installer('confirmed')
        self.assertEqual(finished['status'], 'finished')
        config = installation_config(self.db()['issues'][self.ids['installer']])
        main = next(row for row in self.db()['issues'].values() if row.get('parent_issue_id') == self.ids['installer'] and row['title'].startswith('MAIN DEV:'))
        self.assertEqual(installation_config(main), {})
        self.assertEqual(process_config(main), {'directions': {'message': {key: seed['directions'][0][key] for key in ('questions', 'branch_prefix')}}})
        self.assertTrue({'installed_delegator_id', 'installed_developer_id', 'installed_reviewer_id', 'installed_workspace_id', 'installed_project_id'} <= config.keys())
        self.assertFalse({'root_issue_id', 'installation_issue_id', 'workspace_id', 'project_id'} & config.keys())
        self.assertIn('CEO', self.db()['subscribers'][main['id']])
        self.assertEqual(self.db()['issues'][self.ids['installer']]['status'], 'done')
        self.assertEqual(main['status'], 'in_progress')
        self.assertNotIn(seed['directions'][0]['questions'][0], self.db()['projects'][self.ids['project']]['description'])
        before = self.db()
        self.assertEqual(self.installer()['status'], 'finished')
        self.assertEqual(set(self.db()['issues']), set(before['issues']))
        self.assertEqual(set(self.db()['agents']), set(before['agents']))

    def test_install_removes_only_legacy_description_block_and_main_reads_metadata(self):
        db = self.db()
        legacy = ('\n\n<!-- featssship:installation -->\n'
                  'Acceptance: Does message.txt exactly match the requested message format?\n'
                  '<!-- /featssship:installation -->')
        db['projects'][self.ids['project']]['description'] += legacy + '\nKeep this footer.'
        db['issues'][self.ids['root']]['description'] += legacy
        self.db_path.write_text(json.dumps(db))
        answers = self.read_answers()
        answers['directions'].append({'name': 'other', 'scope': 'other/', 'test_command': 'true',
                                      'questions': ['Only the other direction sees this question.'], 'branch_prefix': 'feat/other'})
        self.write_answers(answers)
        self.install()
        db = self.db()
        self.assertTrue(db['projects'][self.ids['project']]['description'].startswith('Existing project context.'))
        self.assertIn('Keep this footer.', db['projects'][self.ids['project']]['description'])
        self.assertNotIn('Acceptance:', db['projects'][self.ids['project']]['description'])
        main = db['issues'][self.ids['root']]
        self.assertNotIn('Acceptance:', main['description'])
        self.assertEqual(main['metadata']['unrelated'], 'preserve')
        self.assertEqual(main['status'], 'in_progress')
        self.assertEqual(main['title'], 'MAIN DEV: Existing shipping root')
        self.assertFalse((self.root_package / 'installation.json').exists())
        self.assertFalse((ROOT / '.multica/featssship/installer/installation.json').exists())
        self.assertEqual(set(process_config(main)['directions']['message']), {'questions', 'branch_prefix'})
        process = process_config(main)
        process['sandbox'] = {'policy': 'inherited-native-policy'}
        db['issues'][self.ids['root']]['metadata'][PROCESS_KEY] = json.dumps(process)
        self.db_path.write_text(json.dumps(db))
        self.invoke(self.root_package, role='delegator', issue=self.ids['root'])
        self.invoke(self.root_package, 'propose', '--name', 'ship-message', '--request', 'Write shipped.',
                    '--direction', 'message', role='delegator', issue=self.ids['root'])
        spec, _ = self.record('spec', self.ids['root'])
        for key in ('scope', 'test_command'):
            self.assertEqual(spec[key], self.config['directions'][0][key])
        self.assertEqual(spec['question'], self.config['directions'][0]['questions'][0])
        self.invoke(self.root_package, 'dispatch', role='delegator', issue=self.ids['root'])
        child = self.db()['issues'][self.record('dispatch', self.ids['root'])[0]['issue_id']]
        self.assertIn('Acceptance: ' + spec['question'], child['description'])
        process = process_config(child)
        self.assertEqual(set(process), {'questions', 'branch', 'parent_branch', 'sandbox'})
        self.assertEqual(process['questions'], self.config['directions'][0]['questions'])
        self.assertEqual(process['parent_branch'], 'main')
        self.assertEqual(process['sandbox'], {'policy': 'inherited-native-policy'})
        self.assertNotIn('Only the other direction', json.dumps(process))
        self.assertNotIn('featssship:binding', child['description'])

    def test_install_preserves_unrelated_main_skill(self):
        db = self.db()
        skill_id = str(uuid.uuid4())
        db['skills'][skill_id] = {'id': skill_id, 'name': 'existing-main-skill', 'files': {}}
        db['bindings'][self.ids['main']] = [skill_id]
        self.db_path.write_text(json.dumps(db))
        self.install()
        self.assertIn(skill_id, self.db()['bindings'][self.ids['main']])
        self.assertEqual(self.db()['skills'][skill_id], db['skills'][skill_id])
        self.assertEqual(len(self.db()['skills']), 3)

    def test_one_point_grilling_and_cross_task_dispatch_recovery(self):
        self.install()
        task = self.propose(github=True)
        self.assertEqual(len(self.db()['issues']), 2)
        self.assertEqual(self.db()['github_calls'], [])
        inspected = self.invoke(self.root_package, role='delegator', issue=self.ids['root'], task=task)
        self.assertEqual(inspected['status'], 'grilling')
        self.assertEqual([step['command'].split()[-1] for step in inspected['next_step']], ['edit', 'dispatch'])
        original = unpack(next(row for row in self.db()['comments'] if row['id'] == self.spec_id)['content'], 'spec')
        for flags in ((), ('--question', 'New question?', '--scope', 'new scope'), ('--question', '')):
            denied = self.invoke(self.root_package, 'edit', *flags, role='delegator', issue=self.ids['root'], task=task, ok=False)
            self.assertIn('error', denied)
        self.assertEqual(len([row for row in self.db()['comments'] if unpack(row['content'], 'spec')]), 1)
        reply_id = self.ask_and_reply('Should acceptance inspect the first line?', 'Yes, inspect the first line.')
        task = str(uuid.uuid4())
        self.invoke(self.root_package, '--thread', reply_id, '--spec', self.spec_id,
                    role='delegator', issue=self.ids['root'], task=task)
        reopened = self.invoke(self.root_package, role='delegator', issue=self.ids['root'], task=task)
        self.assertEqual(self.record('spec', self.ids['root'])[0], original)
        self.assertEqual(reopened['status'], 'grilling')
        revised = self.invoke(self.root_package, 'edit', '--question', 'Does the first line say shipped?',
                              role='delegator', issue=self.ids['root'], task=task, trigger=reply_id)
        self.assertEqual(revised['status'], 'grilling')
        spec, row = self.record('spec', self.ids['root'])
        self.assertEqual(spec, {**original, 'question': 'Does the first line say shipped?'})
        self.spec_id = row['id']
        reply_id = self.ask_and_reply('Should scope include its focused tests?', 'Yes.')
        self.invoke(self.root_package, '--thread', reply_id, role='delegator', issue=self.ids['root'], task=task)
        revised = self.invoke(self.root_package, 'edit', '--scope', 'message.txt and its focused tests',
                              role='delegator', issue=self.ids['root'], task=task, trigger=reply_id)
        spec, row = self.record('spec', self.ids['root'])
        self.assertEqual(spec, {**original, 'question': 'Does the first line say shipped?',
                               'scope': 'message.txt and its focused tests'})
        self.spec_id = row['id']
        dispatched = self.invoke(self.root_package, 'dispatch', role='delegator', issue=self.ids['root'], task=task,
                                 trigger=reply_id)
        feature_id = self.record('dispatch', self.ids['root'])[0]['issue_id']
        binding = process_config(self.db()['issues'][feature_id])
        self.assertIn('Scope: message.txt and its focused tests', self.db()['issues'][feature_id]['description'])
        self.assertIn('Acceptance: Does the first line say shipped?', self.db()['issues'][feature_id]['description'])
        self.assertIn(self.config['feature_skill_id'], self.db()['bindings'][self.config['reviewer_id']])
        self.assertEqual(self.db()['issues'][feature_id]['status'], 'todo')
        self.assertNotIn('sop.' + self.root_package.name, self.db()['issues'][self.ids['root']]['metadata'])
        task = str(uuid.uuid4())
        self.invoke(self.root_package, '--thread', reply_id, '--spec', self.spec_id,
                    role='delegator', issue=self.ids['root'], task=task)
        self.invoke(self.root_package, 'propose', role='delegator', issue=self.ids['root'], task=task)
        reused = self.invoke(self.root_package, 'dispatch', role='delegator', issue=self.ids['root'], task=task)
        self.assertEqual(self.record('dispatch', self.ids['root'])[0]['issue_id'], feature_id)
        self.assertEqual(len(self.db()['issues']), 3)



if __name__ == '__main__':
    unittest.main()
