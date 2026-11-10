import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import QUESTIONS, block, unpack


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
        self.ids = {name: str(uuid.uuid4()) for name in ('workspace', 'project', 'root', 'main', 'runtime')}
        self.db_path = self.base / 'native.json'
        db = {'workspace_id': self.ids['workspace'], 'calls': [], 'agents': {
            self.ids['main']: {'id': self.ids['main'], 'runtime_id': self.ids['runtime'], 'workspace_id': self.ids['workspace']}},
            'skills': {}, 'bindings': {}, 'projects': {self.ids['project']: {'id': self.ids['project'],
            'workspace_id': self.ids['workspace'], 'description': 'Existing project context.'}},
            'issues': {self.ids['root']: {'id': self.ids['root'], 'workspace_id': self.ids['workspace'],
            'project_id': self.ids['project'], 'title': 'Existing shipping root', 'description': 'Existing root context.',
            'assignee_id': self.ids['main'], 'assignee_type': 'agent', 'status': 'in_progress', 'labels': [{'name': 'manual'}], 'metadata': {'unrelated': 'preserve'}}}, 'comments': [],
            'github_calls': [], 'github': {'url': 'https://github.com/owner/requests/issues/42',
            'title': 'Ship the message', 'body': 'Requirement: write shipped. Verification: read message.txt.',
            'state': 'OPEN', 'comments': [], 'remote': str(self.remote)}}
        self.db_path.write_text(json.dumps(db))
        binaries = self.base / 'bin'
        binaries.mkdir()
        script = binaries / 'multica'
        script.write_text('#!' + sys.executable + '\nimport runpy\nrunpy.run_path(' + repr(str(ROOT / 'tests/fake_multica.py')) + ", run_name='__main__')\n")
        script.chmod(0o755)
        self.env.update(PATH=str(binaries) + os.pathsep + os.environ['PATH'], FEATSSSHIP_FAKE_DB=str(self.db_path))
        self.config_path = self.base / 'answers.json'
        config = {'workspace_id': self.ids['workspace'], 'project_id': self.ids['project'], 'root_issue_id': self.ids['root'],
                  'repository': str(self.remote), 'developer': {'name': 'Developer', 'runtime_id': self.ids['runtime'], 'model': 'fixture'},
                  'reviewer': {'name': 'Reviewer', 'runtime_id': self.ids['runtime'], 'model': 'fixture'},
                  'directions': [{'name': 'message', 'scope': 'message.txt', 'question': 'Does message.txt say shipped?',
                                  'test_command': 'python3 -c "from pathlib import Path; assert Path(\'message.txt\').exists()"'}]}
        self.config_path.write_text(json.dumps(config))

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

    def record(self, kind, issue=None):
        for row in reversed(self.db()['comments']):
            if row['issue_id'] == (issue or self.feature_id):
                data = unpack(row['content'], kind)
                if data:
                    return data, row
        self.fail('Missing native record: ' + kind)

    def install(self):
        result = self.call(sys.executable, str(ROOT / 'install.py'), '--config', str(self.config_path))
        self.config = json.loads(self.config_path.read_text())
        self.root_package = self.repo / '.agents/skills' / ('multica-featssship-' + self.ids['project'][:8])
        self.developer = self.repo / '.agents/skills/multica-featssship-develop-review'
        from packages import build
        self.reviewer = build('feature', self.base / 'reviewer-skill')
        return json.loads(result.stdout)

    def invoke(self, package, *args, role='developer', issue=None, task=None, trigger=None, ok=True, entry=False, plain=False):
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
        self.invoke(self.root_package, role='main', issue=self.ids['root'], task=task)
        title = 'Message: ship requested text'
        if mirror:
            title = '[' + title + '](' + self.db()['github']['url'] + ')'
        options = ['--github-issue', self.db()['github']['url']] if github else []
        output = self.invoke(self.root_package, 'propose', '--title', title, '--request', 'Write shipped in message.txt.',
                             '--direction', 'message', '--scope', 'message.txt', '--question', question,
                             *options, role='main', issue=self.ids['root'], task=task)
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
        output = self.invoke(self.root_package, 'dispatch', role='main', issue=self.ids['root'], task=task)
        self.feature_id = self.record('dispatch', self.ids['root'])[0]['issue_id']
        self.binding = unpack(self.db()['issues'][self.feature_id]['description'], 'binding')
        self.call('git', 'fetch', 'origin', self.binding['branch'])
        self.call('git', 'switch', '-c', self.binding['branch'], 'FETCH_HEAD')
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
        result = self.invoke(self.developer, 'submit', '--summary', 'Updated message.txt: ' + text, plain=True)
        self.assertEqual(result.stdout, 'Submitted to Reviewer; end this turn.\n')
        self.assertEqual(result.stderr, '')
        return commit

    def review(self, verdict):
        self.invoke(self.reviewer, role='reviewer')
        result = self.invoke(self.reviewer, verdict, '--finding',
                           'Acceptance, necessary additions and scope verified.' if verdict == 'approve' else
                           'Replace almost with shipped.', role='reviewer', plain=True)
        self.assertEqual(result.stdout, 'Verdict sent to Developer; end this turn.\n')
        self.assertEqual(result.stderr, '')
        return self.state()['output']

    def integrate(self):
        self.invoke(self.developer)
        return self.invoke(self.developer, 'integrate')

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
        self.assertEqual(set(self.binding), {'developer_id', 'reviewer_id', 'branch', 'test_command'})
        for role in ('developer', 'reviewer'):
            self.assertIn(self.config['feature_skill_id'], self.db()['bindings'][self.config[role + '_id']])
        self.invoke(self.developer)
        before = self.state()
        for event in ('init', 'quit'):
            denied = self.invoke(self.reviewer, *([] if event == 'init' else [event]), role='reviewer', ok=False, plain=True)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(denied.stdout, '')
            self.assertIn('belongs to developer', denied.stderr)
            self.assertEqual(self.state(), before)
        first_commit = self.submit('almost')
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
        self.assertEqual(self.integrate()['status'], 'finished')
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
        self.assertEqual(self.invoke(self.developer)['status'], 'finished')
        self.assertEqual(len(self.parent_notes()), 1)

    def test_manual_check_reports_to_parent_and_finishes(self):
        self.install(); self.dispatch(); self.submit('shipped')
        db = self.db()
        db['issues'][self.feature_id]['labels'] = [{'name': 'manual'}]
        self.db_path.write_text(json.dumps(db))
        self.assertEqual(self.review('approve')['status'], 'integrate')
        self.assertEqual(self.integrate()['status'], 'finished')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'baseline\n')
        self.assertIn('Manual check required', self.parent_notes()[0])
        self.assertEqual(self.state(), {})

    def test_review_graph_shows_default_and_configured_questions(self):
        self.assertEqual(QUESTIONS, (
            'Does the solution preserve the requested demand without shifting scope?',
            'Are the additions necessary for the requested outcome?',
        ))
        defaults = '\n'.join('- ' + q for q in QUESTIONS)
        self.install()
        question = 'Does message.txt say "shipped" rather than <draft>?'
        self.dispatch(question=question)
        snapshot = self.base / 'review.html'
        code = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import wrapper
wrapper.upload_artifact = lambda filename, content, **kwargs: Path(sys.argv[2]).write_text(content)
raise SystemExit(wrapper.main(sys.argv[3:]))
"""
        env = {**self.env, 'MULTICA_AGENT_ID': self.config['developer_id'],
               'MULTICA_ISSUE_ID': self.feature_id, 'MULTICA_WORKSPACE_ID': self.ids['workspace'],
               'MULTICA_SERVER_URL': 'http://fixture.invalid', 'MULTICA_TOKEN': 'fixture-token'}

        def step(*args):
            result = self.call(sys.executable, '-c', code, str(self.developer), str(snapshot), *args, env=env)
            self.assertEqual(result.stderr, '')
            payload = re.search(r'<script id="sop-data" type="application/json">(.*?)</script>',
                                snapshot.read_text(), re.S)[1]
            if args:
                self.assertEqual(result.stdout, 'Submitted to Reviewer; end this turn.\n')
            else:
                self.assertEqual(json.loads(result.stdout)['status'], 'develop')
            return self.state()['output'], json.loads(payload)

        _, graph = step()
        self.assertEqual(graph['decision']['status'], 'develop')
        self.assertIn(defaults, graph['nodes']['review']['instruction'])
        (self.repo / 'message.txt').write_text('shipped\n')
        self.commit('shipped')
        output, graph = step('submit', '--summary', 'Wrote shipped in message.txt.')
        self.assertEqual(graph['decision'], output)
        self.assertEqual(output['status'], 'review')
        self.assertEqual(self.state()['output'], output)
        for expected in (defaults, question, 'shared folder and branch'):
            self.assertIn(expected, graph['nodes']['review']['instruction'])
        self.assertNotIn('Does the delivered behavior satisfy the request and acceptance evidence?', snapshot.read_text())
        self.assertNotIn('featssship:binding', output['instruction'])
        self.assertNotIn('Developer:', output['instruction'])
        self.assertNotIn('Merge and test', output['next_step'][0]['instruction'])
        self.assertEqual(self.invoke(self.reviewer, role='reviewer')['instruction'], output['instruction'])
        self.assertEqual(self.call('git', 'branch', '--show-current').stdout.strip(), self.binding['branch'])
        self.assertEqual(self.call('git', 'status', '--porcelain').stdout, '')

    def test_conflict_reports_to_parent_without_losing_feature(self):
        self.install(); self.dispatch()
        commit = self.submit('shipped')
        self.advance_main('message.txt', 'Conflicting main change\n')
        self.assertEqual(self.review('approve')['status'], 'integrate')
        self.assertEqual(self.integrate()['status'], 'finished')
        self.assertIn('Manual check required', self.parent_notes()[0])
        self.assertEqual(self.call('git', 'rev-parse', 'HEAD').stdout.strip(), commit)
        self.assertEqual((self.repo / 'message.txt').read_text(), 'shipped\n')
        self.assertEqual(self.call('git', 'status', '--porcelain').stdout, '')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'Conflicting main change\n')

    def test_changed_revision_rejected(self):
        self.install(); self.dispatch(); self.submit('shipped')
        (self.repo / 'message.txt').write_text('unreviewed\n')
        self.commit('unreviewed', amend=True)
        before = self.state()['commit']
        rejected = self.invoke(self.reviewer, 'approve', '--finding', 'Looks fine', role='reviewer', ok=False)
        self.assertIn('exact submitted revision', rejected['error']['message'])
        self.assertEqual(self.parent_notes(), [])
        self.assertEqual(self.state()['commit'], before)

    def test_reviewer_only_reads_and_developer_integrates_approved_head(self):
        self.install(); self.dispatch(); self.submit('shipped')
        self.invoke(self.reviewer, role='reviewer')
        code = """import sys
sys.path.insert(0, sys.argv[1])
import common, wrapper
git = common.git
def read_only(repo, *words):
    assert words[0] in {'status', 'branch', 'rev-parse'}, words
    return git(repo, *words)
def no_test(*args):
    raise AssertionError('Reviewer must not run tests')
common.git, common.test = read_only, no_test
raise SystemExit(wrapper.main(['approve', '--finding', 'Scope and necessity verified.']))
"""
        env = {**self.env, 'MULTICA_AGENT_ID': self.config['reviewer_id'],
               'MULTICA_ISSUE_ID': self.feature_id, 'MULTICA_WORKSPACE_ID': self.ids['workspace']}
        result = self.call(sys.executable, '-c', code, str(self.reviewer), env=env)
        self.assertEqual(result.stdout, 'Verdict sent to Developer; end this turn.\n')
        self.assertEqual(result.stderr, '')
        approved = self.state()
        self.assertEqual(approved['status'], 'integrate')
        self.assertEqual(self.parent_notes(), [])
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'baseline\n')
        denied = self.invoke(self.reviewer, 'integrate', role='reviewer', plain=True, ok=False)
        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(denied.stdout, '')
        self.assertIn('belongs to developer', denied.stderr)
        self.assertEqual(self.state(), approved)
        (self.repo / 'message.txt').write_text('unreviewed\n')
        self.commit('unreviewed', amend=True)
        rejected = self.invoke(self.developer, 'integrate', ok=False)
        self.assertIn('exact approved revision', rejected['error']['message'])
        self.assertEqual(self.parent_notes(), [])

    def test_failed_independent_check_reports_to_main(self):
        self.install(); self.dispatch(); self.submit('shipped')
        db = self.db()
        binding = {**self.binding, 'test_command': 'false'}
        db['issues'][self.feature_id]['description'] = db['issues'][self.feature_id]['description'].replace(
            block('binding', self.binding), block('binding', binding))
        self.db_path.write_text(json.dumps(db))
        self.assertEqual(self.review('approve')['status'], 'integrate')
        self.assertEqual(self.integrate()['status'], 'finished')
        self.assertIn('Configured check failed', self.parent_notes()[0])
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'baseline\n')

    def test_package_upgrade_preserves_settings_state_and_help(self):
        from packages import build
        self.install()
        self.dispatch()
        self.submit('shipped')
        # MAIN has completed; feature state remains shared and live in review.
        package = self.developer
        state = self.state()
        (package / 'config.json').write_text('{"DEBUG": false}')
        legacy = package / '.state/legacy-task.json'
        legacy.parent.mkdir()
        legacy.write_text('{"status":"implement"}')
        build('feature', package)
        self.assertEqual(self.state(), state)
        self.assertEqual(legacy.read_text(), '{"status":"implement"}')
        self.assertEqual(json.loads((package / 'config.json').read_text()), {'DEBUG': False})
        before = len([c for c in self.db()['calls'] if c[:2] == ['issue', 'metadata']])
        for role in ('developer', 'reviewer'):
            self.assertEqual(self.invoke(package, '--help', role=role), state['output'])
        # A receiving skill directory rebinds callbacks, without copying state/files.
        receiving = build('feature', self.base / 'receiving')
        output = self.invoke(receiving, '--help', role='reviewer', entry=True)
        self.assertEqual(output['status'], 'review')
        self.assertTrue(all(str(receiving / 'wrapper.py') in c['command'] for c in output['next_step']))
        self.assertFalse((receiving / '.state').exists())
        self.assertEqual(self.state(), state)
        after = len([c for c in self.db()['calls'] if c[:2] == ['issue', 'metadata']])
        self.assertEqual(before, after)
        self.install()
        self.assertEqual(self.state(), state)
        self.assertEqual(json.loads((package / 'config.json').read_text()), {'DEBUG': False})

    def test_preview_failure_preserves_action_result(self):
        self.install()
        (self.root_package / 'config.json').write_text('{"DEBUG": true}')
        code = """import json, sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import wrapper
with patch(sys.argv[2], return_value=json.loads(sys.argv[3])):
    raise SystemExit(wrapper.main(sys.argv[4:]))
"""
        for target, value, message in (
            ('wrapper.shutil.which', None, 'Cannot install graphviz: no supported package manager on PATH.'),
            ('sop.Option.diagram', 'digraph broken { a -> }', 'Invalid DOT diagram:'),
        ):
            with self.subTest(failure=target):
                task = str(uuid.uuid4())
                db = self.db()
                db['issues'][self.ids['root']]['metadata'] = {'unrelated': 'preserve'}
                self.db_path.write_text(json.dumps(db))
                self.invoke(self.root_package, role='main', issue=self.ids['root'], task=task)
                before = len(self.db()['comments'])
                env = {**self.env, 'MULTICA_TASK_ID': task, 'MULTICA_AGENT_ID': self.config['main_id'],
                       'MULTICA_ISSUE_ID': self.ids['root'], 'MULTICA_WORKSPACE_ID': self.ids['workspace'],
                       'MULTICA_SERVER_URL': 'http://fixture.invalid', 'MULTICA_TOKEN': 'fixture-token'}
                result = self.call(sys.executable, '-c', code, str(self.root_package), target, json.dumps(value),
                                   'propose', '--title', 'Ship message', '--request', 'Write shipped.',
                                   '--direction', 'message', '--scope', 'message.txt',
                                   '--question', 'Does message.txt say shipped?', env=env)
                output = json.loads(result.stdout)
                self.assertEqual(output['status'], 'grilling')
                self.assertNotIn('data', output)
                self.assertNotIn('error', output)
                self.assertIn('Live artifact update failed: ' + message, result.stderr)
                saved = self.state(self.ids['root'], self.root_package)
                self.assertEqual(saved['status'], 'grilling')
                self.assertEqual(saved['output'], output)
                self.assertEqual(self.invoke(self.root_package, '--help', role='main',
                                             issue=self.ids['root'], task=task), output)
                self.assertEqual(len(self.db()['comments']), before + 1)

    def test_install_rejects_self_review(self):
        config = json.loads(self.config_path.read_text())
        config.update(developer_id=self.ids['main'], reviewer_id=self.ids['main'])
        self.config_path.write_text(json.dumps(config))
        result = self.call(sys.executable, str(ROOT / 'install.py'), '--config', str(self.config_path), ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.db()['agents']), 1)

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
        self.assertEqual(len(self.db()['issues']), 1)
        self.assertEqual(self.db()['github_calls'], [])
        inspected = self.invoke(self.root_package, role='main', issue=self.ids['root'], task=task)
        self.assertEqual(inspected['status'], 'grilling')
        self.assertEqual([step['command'].split()[-1] for step in inspected['next_step']], ['edit', 'dispatch'])
        original = unpack(next(row for row in self.db()['comments'] if row['id'] == self.spec_id)['content'], 'spec')
        for flags in ((), ('--question', 'New question?', '--scope', 'new scope'), ('--question', '')):
            denied = self.invoke(self.root_package, 'edit', *flags, role='main', issue=self.ids['root'], task=task, ok=False)
            self.assertIn('error', denied)
        self.assertEqual(len([row for row in self.db()['comments'] if unpack(row['content'], 'spec')]), 1)
        reply_id = self.ask_and_reply('Should acceptance inspect the first line?', 'Yes, inspect the first line.')
        task = str(uuid.uuid4())
        self.invoke(self.root_package, '--thread', reply_id, '--spec', self.spec_id,
                    role='main', issue=self.ids['root'], task=task)
        reopened = self.invoke(self.root_package, role='main', issue=self.ids['root'], task=task)
        self.assertEqual(self.record('spec', self.ids['root'])[0], original)
        self.assertEqual(reopened['status'], 'grilling')
        revised = self.invoke(self.root_package, 'edit', '--question', 'Does the first line say shipped?',
                              role='main', issue=self.ids['root'], task=task, trigger=reply_id)
        self.assertEqual(revised['status'], 'grilling')
        spec, row = self.record('spec', self.ids['root'])
        self.assertEqual(spec, {**original, 'question': 'Does the first line say shipped?'})
        self.spec_id = row['id']
        reply_id = self.ask_and_reply('Should scope include its focused tests?', 'Yes.')
        self.invoke(self.root_package, '--thread', reply_id, role='main', issue=self.ids['root'], task=task)
        revised = self.invoke(self.root_package, 'edit', '--scope', 'message.txt and its focused tests',
                              role='main', issue=self.ids['root'], task=task, trigger=reply_id)
        spec, row = self.record('spec', self.ids['root'])
        self.assertEqual(spec, {**original, 'question': 'Does the first line say shipped?',
                               'scope': 'message.txt and its focused tests'})
        self.spec_id = row['id']
        dispatched = self.invoke(self.root_package, 'dispatch', role='main', issue=self.ids['root'], task=task,
                                 trigger=reply_id)
        feature_id = self.record('dispatch', self.ids['root'])[0]['issue_id']
        binding = unpack(self.db()['issues'][feature_id]['description'], 'binding')
        self.assertIn('Scope: message.txt and its focused tests', self.db()['issues'][feature_id]['description'])
        self.assertIn('Acceptance: Does the first line say shipped?', self.db()['issues'][feature_id]['description'])
        self.assertIn(self.config['feature_skill_id'], self.db()['bindings'][self.config['reviewer_id']])
        self.assertEqual(self.db()['issues'][feature_id]['status'], 'todo')
        self.assertNotIn('sop.' + self.root_package.name, self.db()['issues'][self.ids['root']]['metadata'])
        task = str(uuid.uuid4())
        self.invoke(self.root_package, '--thread', reply_id, '--spec', self.spec_id,
                    role='main', issue=self.ids['root'], task=task)
        self.invoke(self.root_package, 'propose', role='main', issue=self.ids['root'], task=task)
        reused = self.invoke(self.root_package, 'dispatch', role='main', issue=self.ids['root'], task=task)
        self.assertEqual(self.record('dispatch', self.ids['root'])[0]['issue_id'], feature_id)
        self.assertEqual(len(self.db()['issues']), 2)



if __name__ == '__main__':
    unittest.main()
