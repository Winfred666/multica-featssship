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
sys.path.insert(0, str(ROOT / 'installation'))
from common import CONFIG_KEY, DELEGATION_KEY, DISPATCH_KEY, comment, config_ref, feature_branch, request_config


class DeliveryRoutingTests(unittest.TestCase):
    def test_blocked_recipient_is_not_a_successful_handoff(self):
        for status in ('queued', 'coalesced', 'deferred', 'steered', 'blocked'):
            response = {'id': 'posted', 'trigger_outcomes': [
                {'target_id': 'recipient', 'status': status}]}
            with self.subTest(status=status), patch('common.cli', side_effect=[[], response]):
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
        self.ids = {name: str(uuid.uuid4()) for name in ('workspace', 'project', 'main', 'runtime', 'installer')}
        self.db_path = self.base / 'native.json'
        db = {'workspace_id': self.ids['workspace'], 'calls': [], 'agents': {
            self.ids['main']: {'id': self.ids['main'], 'runtime_id': self.ids['runtime'], 'workspace_id': self.ids['workspace'],
                               'model': 'fixture', 'thinking_level': 'high'}},
            'skills': {}, 'bindings': {}, 'projects': {self.ids['project']: {'id': self.ids['project'],
            'workspace_id': self.ids['workspace'], 'description': 'Existing project context.'}},
            'issues': {}, 'comments': [],
            'github_calls': [], 'github': {'url': 'https://github.com/owner/requests/issues/42',
            'title': 'Ship the message', 'body': 'Requirement: write shipped. Verification: read message.txt.',
            'state': 'OPEN', 'comments': [], 'remote': str(self.remote)}}
        db['issues'][self.ids['installer']] = {'id': self.ids['installer'], 'workspace_id': self.ids['workspace'],
            'project_id': self.ids['project'], 'title': 'Install shipping', 'description': '',
            'assignee_id': self.ids['main'], 'assignee_type': 'agent', 'status': 'in_progress', 'labels': [], 'metadata': {}}
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
               'MULTICA_AGENT_ID': self.ids['main'], 'MULTICA_WORKSPACE_ID': self.ids['workspace']}
        result = self.call(sys.executable, str(getattr(self, 'installer_entry', ROOT / 'installation/install.py')), *args, env=env, ok=ok)
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
        audit = self.read_answers()
        root = next(row for row in reversed(list(self.db()['issues'].values())) if row['title'].startswith('MAIN DEV:'))
        self.ids['root'] = root['id']
        self.ids['project'] = root['project_id']
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

    def configure_delegation(self, *, github=False, mirror=False, question='Does message.txt say shipped?'):
        config = {'name': 'ship-message', 'request': 'Write shipped in message.txt.',
                  'direction': 'message', 'scope': 'message.txt', 'question': question}
        if mirror:
            config['title'] = '[Message: ship requested text](' + self.db()['github']['url'] + ')'
        if github:
            config['github_issue'] = self.db()['github']['url']
        db = self.db()
        self.dispatch_thread = str(uuid.uuid4())
        db['comments'].append({'id': self.dispatch_thread, 'issue_id': self.ids['root'],
                               'parent_id': None, 'author_type': 'member', 'content': 'Ship message.'})
        self.db_path.write_text(json.dumps(db))
        self.invoke(self.root_package, '--thread', self.dispatch_thread, '--config', json.dumps(config), role='delegator', issue=self.ids['root'])

    def delegation(self):
        return json.loads(self.db()['issues'][self.ids['root']]['metadata'].get(DISPATCH_KEY, '{}'))

    def dispatch(self, *, github=False, mirror=False, question='Does message.txt say shipped?'):
        self.configure_delegation(github=github, mirror=mirror, question=question)
        output = self.invoke(self.root_package, 'dispatch', role='delegator', issue=self.ids['root'])
        self.feature_id = self.delegation()['issue_id']
        self.binding = request_config(self.document(self.db()['issues'][self.feature_id], DELEGATION_KEY), self.read_answers())
        self.root_repo = self.repo
        common = self.call('git', 'rev-parse', '--path-format=absolute', '--git-common-dir').stdout.strip()
        self.repo = Path(common) / 'featsship' / self.feature_id
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
                           'Acceptance verified: message.txt says shipped.' if verdict == 'approve' else
                           'Replace almost with shipped.', role='reviewer', plain=True)
        manual = self.state()['status'] == 'manual_approve'
        expected = ('Auto review pass, directly and silently exit until superior instruction, if outer confirmation has not been received yet.' if manual else
                    'Rework sent, directly and silently exit' if verdict == 'rework' else
                    None)
        if expected:
            self.assertEqual(result.stdout, expected + '\n')
        else:
            self.assertEqual(json.loads(result.stdout)['status'], 'approve')
        self.assertEqual(result.stderr, '')
        if verdict == 'rework':
            self.assert_delivery(before, self.config['developer_id'], self.feature_id)
        elif not manual:
            self.assertEqual(len(self.db()['comments']), before)
        return self.state()['output']

    def finish(self):
        self.invoke(self.reviewer, role='reviewer')
        before = len(self.db()['comments'])
        result = self.invoke(self.reviewer, 'approve', role='reviewer', plain=True)
        self.repo = self.root_repo
        self.assertEqual(result.stdout, 'Delivery/review/work done this round, exit directly and silently\n')
        self.assertEqual(result.stderr, '')
        self.assertEqual(self.state(), {})
        note = self.db()['comments'][before:]
        self.assertEqual(len(note), 1)
        self.assertEqual(note[0]['issue_id'], self.ids['root'])
        self.assertEqual(note[0]['parent_id'], self.dispatch_thread)
        self.assertIn('[@all](mention://all/all) Note:', note[0]['content'])
        self.assertNotIn('mention://agent/', note[0]['content'])
        self.assertNotIn('Review the', note[0]['content'])
        posted = [call for call in self.db()['calls'] if call[:4] == ['issue', 'comment', 'add', self.ids['root']]][-1]
        self.assertNotIn('--steer', posted)

    def assert_delivery(self, before, recipient, issue):
        rows = self.db()['comments'][before:]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['issue_id'], issue)
        body = rows[0]['content']
        self.assertIn('mention://agent/' + recipient, body)
        self.assertEqual(body.count('mention://agent/'), 1)
        self.assertNotIn('TODO', body)
        if issue != self.feature_id:
            self.assertIn('mention://issue/' + self.feature_id, body)
        self.assertIn('[@' + self.db()['agents'][recipient]['name'] + ']', body)

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

    def test_standalone_bundles_and_packaged_installer(self):
        from packages import build
        env = {**self.env, 'MULTICA_ISSUE_ID': self.ids['installer'],
               'MULTICA_WORKSPACE_ID': self.ids['workspace']}
        for role, relative in (('installation', 'installation'), ('delegation', 'delegation'),
                               ('feature', 'delegation/dev-rev')):
            directory = build(role, self.base / (role + '-package'))
            self.assertEqual(json.loads(self.call(sys.executable, str(directory / 'wrapper.py'),
                                                 '--validate', env=env).stdout)['status'], 'valid')
            help_text = self.call(sys.executable, str(directory / 'wrapper.py'), '--help', env=env).stdout
            self.assertEqual(help_text.strip(), (directory / 'SKILL.md').read_text().split('---', 2)[2].strip())
            package = self.base / (role + '-package')
            (package / 'config.json').write_text('{"DEBUG": false}\n')
            build(role, package)
            self.assertFalse(json.loads((package / 'config.json').read_text())['DEBUG'])
        # Installation must work without importing from the featssship checkout.
        self.installer_entry = self.base / 'installation-package' / 'wrapper.py'
        self.install()
        self.dispatch()
        self.assertEqual(self.invoke(self.developer)['status'], 'develop')

    def test_two_agent_correction_merge_and_minimal_binding(self):
        self.install()
        for package in (self.root_package, self.developer, self.reviewer):
            self.assertIs(json.loads((package / 'config.json').read_text())['DEBUG'], True)
        self.assertEqual(len(self.db()['skills']), 2)
        audit = self.read_answers()
        audit['directions'][0]['test_command'] = 'false'
        self.write_answers(audit)
        self.dispatch()
        self.assertEqual(self.binding['branch'], 'feat/messages/ship-message')
        self.assertEqual(self.call('git', 'ls-remote', '--heads', 'origin', self.binding['branch']).stdout, '')
        for role in ('developer', 'reviewer'):
            self.assertIn(self.config['feature_skill_id'], self.db()['bindings'][self.config[role + '_id']])
        initial = self.invoke(self.developer)
        self.assertEqual(initial['status'], 'develop')
        self.assertEqual(len(initial['next_step']), 3)  # submit, cancel and quit; no prepare.
        before = self.state()
        for event in ('init', 'quit'):
            denied = self.invoke(self.reviewer, *([] if event == 'init' else [event]), role='reviewer', ok=False, plain=True)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(denied.stdout, '')
            self.assertIn('belongs to Developer', denied.stderr)
            self.assertEqual(self.state(), before)
        first_commit = self.submit('almost')
        self.assertNotIn('branch', self.state())  # MAIN's binding is the single source of the name.
        before = self.state()
        for event in ('init', 'approve', 'rework'):
            denied = self.invoke(self.developer, *([] if event == 'init' else [event]), ok=False, plain=True)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(denied.stdout, '')
            self.assertIn('belongs to Reviewer', denied.stderr)
            self.assertEqual(self.state(), before)
        self.assertEqual(self.review('rework')['status'], 'develop')
        commit = self.submit('shipped')
        self.assertNotEqual(first_commit, commit)
        self.advance_main('other.txt', 'Concurrent safe change\n')
        self.assertEqual(self.review('approve')['status'], 'approve')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'baseline\n')
        self.assertEqual(self.parent_notes(), [])
        self.finish()
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'shipped\n')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:other.txt').stdout, 'Concurrent safe change\n')
        self.assertEqual(len(self.parent_notes()), 1)
        self.assertIn('Merged ', self.parent_notes()[0])
        self.assertEqual(self.state(), {})
        self.assertNotIn('sop.' + self.root_package.name, self.db()['issues'][self.ids['root']]['metadata'])
        self.assertEqual(len(self.call('git', 'worktree', 'list', '--porcelain').stdout.split('worktree ')), 2)
        self.assertEqual(self.call('git', 'branch', '--show-current').stdout.strip(), 'main')
        self.assertLessEqual(self.db()['peak_metadata_bytes'], 8192)
        self.assertEqual(self.invoke(self.reviewer, role='reviewer', plain=True).stdout,
                         'Delivery/review/work done this round, exit directly and silently\n')
        self.assertEqual(len(self.parent_notes()), 1)

    def test_manual_check_reports_to_parent_and_finishes(self):
        config = self.read_answers(); config['manual'] = True
        self.write_answers(config)
        self.install(); self.dispatch(); self.submit('shipped')
        self.assertEqual(self.review('approve')['status'], 'manual_approve')
        db = self.db()
        approval = {'id': str(uuid.uuid4()), 'issue_id': self.feature_id, 'parent_id': self.state()['manual_comment_id'],
                    'author_type': 'member', 'author_id': str(uuid.uuid4()),
                    'content': '[@Reviewer](mention://agent/' + self.config['reviewer_id'] + ') Approve.'}
        db['comments'].append(approval); self.db_path.write_text(json.dumps(db))
        self.invoke(self.reviewer, '--thread', approval['id'], role='reviewer')
        self.invoke(self.reviewer, 'approve', '--thread', approval['id'], '--finding', 'Superior approved.', role='reviewer', plain=True)
        self.repo = self.root_repo
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'shipped\n')
        self.assertIn('Merged ', self.parent_notes()[0])
        self.assertEqual(self.state(), {})

    def test_main_named_branch_guards_and_competing_first_push(self):
        config = self.read_answers(); config['manual'] = True
        self.write_answers(config)
        self.install(); self.dispatch()
        self.invoke(self.developer)
        (self.repo / 'message.txt').write_text('shipped\n')
        self.commit('shipped')
        self.call('git', 'switch', '-c', 'wrong-branch', 'origin/main')
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
        # A competing writer changed the reserved branch: do not overwrite it.
        competitor = self.call('git', '--git-dir', str(self.remote), 'commit-tree', 'main^{tree}', '-p', 'main', '-m', 'competing write').stdout.strip()
        self.call('git', '--git-dir', str(self.remote), 'update-ref', 'refs/heads/' + self.binding['branch'], competitor)
        denied = self.invoke(self.developer, 'submit', '--summary', 'name collision', plain=True, ok=False)
        self.assertIn('stale info', denied.stdout)
        self.assertEqual(self.call('git', 'ls-remote', 'origin', self.binding['branch']).stdout.split()[0],
                         competitor)
        self.call('git', '--git-dir', str(self.remote), 'update-ref', 'refs/heads/' + self.binding['branch'],
                  self.db()['issues'][self.feature_id]['metadata']['git_base_commit'])
        self.invoke(self.developer, 'submit', '--summary', 'shipped', plain=True)
        self.call('git', 'switch', '-c', 'other-feature')
        denied = self.invoke(self.reviewer, 'approve', '--finding', 'wrong branch', role='reviewer', plain=True, ok=False)
        self.assertIn('one feature branch selected by MAIN', denied.stdout)
        self.call('git', 'switch', self.binding['branch'])
        self.assertEqual(self.review('approve')['status'], 'manual_approve')

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

    def test_install_reentry_creates_another_main_and_retry_resumes_it(self):
        legacy = self.read_answers()
        self.write_answers(legacy)
        db = self.db()
        db['issues'][self.ids['installer']]['project_id'] = None
        self.db_path.write_text(json.dumps(db))
        result = self.install()
        self.assertIn('delegator', self.read_answers())
        self.assertNotIn('main', self.read_answers())
        self.assertIn('installed_delegator_id', self.read_answers())
        self.assertNotIn('installed_main_id', self.read_answers())
        child = self.db()['issues'][result['root_issue_id']]
        self.assertEqual(child['project_id'], self.db()['issues'][self.ids['installer']]['project_id'])
        self.assertEqual(self.db()['projects'][child['project_id']]['repository'], legacy['repository'])
        self.assertEqual(child['status'], 'backlog')
        self.assertTrue(child['title'].startswith('MAIN DEV:'))
        main = self.db()['agents'][self.config['delegator_id']]
        self.assertNotEqual(main['id'], self.ids['main'])
        self.assertEqual((main['runtime_id'], main['model'], main['thinking_level']),
                         (self.ids['runtime'], 'fixture', 'high'))
        self.assertIn(self.config['delegation_skill_id'], self.db()['bindings'][main['id']])
        before = self.db()
        saved = self.read_answers()
        # Reopen outside the SOP: saved completion, not issue status alone, starts a cycle.
        db = self.db()
        db['issues'][self.ids['installer']]['status'] = 'in_progress'
        self.db_path.write_text(json.dumps(db))
        self.assertEqual(self.installer()['status'], 'grilling')
        self.assertEqual(self.read_answers(), saved)
        self.assertEqual(set(self.db()['issues']), set(before['issues']))
        # A new cycle cannot use the previous human confirmation.
        self.assertIn('Publish the config', self.installer('confirmed', ok=False)['error']['message'])
        self.installer('edit', '--patch', '{}')
        reply = self.installation_reply()
        # Fail after MAIN creation, before completion, then retry from saved metadata.
        db = self.db()
        reviewer = db['agents'].pop(saved['installed_reviewer_id'])
        self.db_path.write_text(json.dumps(db))
        self.assertIn('error', self.installer('--thread', reply, 'confirmed', ok=False))
        pending = self.db()
        new_ids = set(pending['issues']) - set(before['issues'])
        self.assertEqual(len(new_ids), 1)
        second = new_ids.pop()
        self.assertEqual(pending['issues'][child['id']], before['issues'][child['id']])
        self.assertEqual(self.installer()['status'], 'grilling')
        db = self.db(); db['agents'][reviewer['id']] = reviewer
        self.db_path.write_text(json.dumps(db))
        self.assertEqual(self.installer('confirmed')['status'], 'finished')
        self.assertEqual(set(self.db()['issues']), set(pending['issues']))
        self.assertEqual(set(self.db()['agents']), set(before['agents']))
        self.assertEqual(set(self.db()['skills']), set(before['skills']))
        self.assertEqual(self.read_answers(), saved)
        self.assertEqual(self.db()['issues'][child['id']], before['issues'][child['id']])
        self.assertEqual(config_ref(self.db()['issues'][second]), config_ref(child))
        self.assertEqual(sum(call[:2] == ['project', 'create'] for call in self.db()['calls']), 1)

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
        saved = self.read_answers()
        self.assertEqual(self.installer()['status'], 'grilling')
        self.assertEqual(self.read_answers(), saved)

    def test_install_preserves_project_context_and_delegation_uses_shared_config(self):
        db = self.db()
        db['projects'][self.ids['project']]['description'] += '\nKeep this footer.'
        self.db_path.write_text(json.dumps(db))
        answers = self.read_answers()
        answers['sandbox'] = {'policy': 'inherited-native-policy'}
        self.write_answers(answers)
        self.install()
        self.assertIn('Keep this footer.', self.db()['projects'][self.ids['project']]['description'])
        self.dispatch()
        self.assertEqual(self.binding['sandbox'], answers['sandbox'])
        self.assertEqual(self.binding['source'], config_ref(self.db()['issues'][self.ids['installer']]))
        self.assertEqual(config_ref(self.db()['issues'][self.feature_id], DELEGATION_KEY),
                         config_ref(self.db()['issues'][self.ids['root']], DELEGATION_KEY))

    def test_install_preserves_unrelated_main_skill(self):
        config = self.read_answers(); config['delegator']['id'] = self.ids['main']
        self.write_answers(config)
        db = self.db()
        skill_id = str(uuid.uuid4())
        db['skills'][skill_id] = {'id': skill_id, 'name': 'existing-main-skill', 'files': {}}
        db['bindings'][self.ids['main']] = [skill_id]
        self.db_path.write_text(json.dumps(db))
        self.install()
        self.assertIn(skill_id, self.db()['bindings'][self.ids['main']])
        self.assertEqual(self.db()['skills'][skill_id], db['skills'][skill_id])
        self.assertEqual(len(self.db()['skills']), 3)

    def test_grilling_and_cross_task_dispatch_recovery(self):
        self.install()
        self.dispatch_thread = str(uuid.uuid4())
        self.invoke(self.root_package, '--thread', self.dispatch_thread, '--config', '{"direction":"message"}',
                    role='delegator', issue=self.ids['root'])
        incomplete = self.invoke(self.root_package, 'dispatch', role='delegator', issue=self.ids['root'])
        self.assertEqual(incomplete['status'], 'grilling')
        self.assertNotIn('issue_id', self.delegation())
        patch = {'name': 'ship-message', 'request': 'Write shipped.', 'question': 'Does the first line say shipped?',
                 'scope': 'message.txt and its focused tests'}
        self.invoke(self.root_package, 'edit', '--patch', json.dumps(patch), role='delegator', issue=self.ids['root'])
        saved = self.document(self.db()['issues'][self.ids['root']], DELEGATION_KEY)
        self.invoke(self.root_package, '--help', role='delegator', issue=self.ids['root'], plain=True)
        self.invoke(self.root_package, 'dispatch', role='delegator', issue=self.ids['root'])
        feature_id = self.delegation()['issue_id']
        child = self.db()['issues'][feature_id]
        self.assertIn('Scope: message.txt and its focused tests', child['description'])
        self.assertEqual(child['status'], 'todo')
        self.assertTrue(self.delegation()['dispatched'])
        self.assertEqual(self.document(child, DELEGATION_KEY), {**saved, 'direction': 'message', 'branch': 'feat/messages/ship-message', 'dispatch_thread': self.dispatch_thread})
        self.invoke(self.root_package, role='delegator', issue=self.ids['root'])
        self.invoke(self.root_package, 'dispatch', role='delegator', issue=self.ids['root'])
        self.assertEqual(self.delegation()['issue_id'], feature_id)
        self.assertEqual(len(self.db()['issues']), 3)


if __name__ == '__main__':
    unittest.main()
