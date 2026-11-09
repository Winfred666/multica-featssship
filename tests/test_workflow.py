import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import block, unpack


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
            'assignee_id': self.ids['main'], 'assignee_type': 'agent', 'status': 'in_progress', 'labels': [{'name': 'manual'}]}}, 'comments': []}
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

    def install(self):
        result = self.call(sys.executable, str(ROOT / 'install.py'), '--config', str(self.config_path))
        self.config = json.loads(self.config_path.read_text())
        self.root_package = self.repo / '.agents/skills' / ('multica-featssship-' + self.ids['project'][:8])
        self.developer = self.repo / '.agents/skills/multica-featssship-developer'
        return json.loads(result.stdout)

    def invoke(self, package, *args, role='developer', issue=None, task=None, trigger=None, ok=True, entry=False):
        self.task = task or str(uuid.uuid4())
        env = {**self.env, 'MULTICA_TASK_ID': self.task, 'MULTICA_AGENT_ID': self.config[role + '_id'],
               'MULTICA_ISSUE_ID': issue or self.feature_id, 'MULTICA_WORKSPACE_ID': self.ids['workspace']}
        if trigger:
            env['FEATSSSHIP_TRIGGER'] = trigger
        result = self.call(sys.executable, str(package / ('entry.py' if entry else 'wrapper.py')), *args, env=env, ok=ok)
        output = json.loads(result.stdout)
        if ok:
            self.assertNotIn('error', output, output)
        return output

    def dispatch(self):
        task = str(uuid.uuid4())
        self.invoke(self.root_package, role='main', issue=self.ids['root'], task=task)
        output = self.invoke(self.root_package, 'dispatch', '--title', 'Message: ship requested text', '--request', 'Write shipped in message.txt.',
                             '--direction', 'message', role='main', issue=self.ids['root'], task=task)
        self.feature_id = output['data']['issue_id']
        self.binding = unpack(self.db()['issues'][self.feature_id]['description'], 'binding')
        return output

    def resume(self):
        task = str(uuid.uuid4())
        self.invoke(self.developer, task=task)
        output = self.invoke(self.developer, 'resume', task=task)
        return task, output

    def submit(self, text, task=None):
        task = task or self.resume()[0]
        self.invoke(self.developer, 'prepare', task=task)
        (self.repo / 'message.txt').write_text(text + '\n')
        commit = self.commit(text, amend=hasattr(self, 'submission_id'))
        output = self.invoke(self.developer, 'submit', '--summary', 'Updated the message using the existing text file.', task=task)
        self.submission_id = output['data']['submission_id']
        # Emulate the daemon materializing the newly imported, independent skill.
        skill = self.db()['skills'][self.binding['reviewer_skill_id']]
        self.reviewer = self.base / ('reviewer-' + str(uuid.uuid4()))
        self.reviewer.mkdir()
        for name, content in skill['files'].items():
            destination = self.reviewer / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
        return commit

    def review(self, verdict):
        task = str(uuid.uuid4())
        self.invoke(self.reviewer, '--thread', self.submission_id, role='reviewer', task=task, trigger=self.submission_id, entry=True)
        self.reviewer = self.repo / '.agents/skills' / ('multica-featssship-review-' + self.feature_id)
        output = self.invoke(self.reviewer, 'prepare', role='reviewer', task=task, trigger=self.submission_id)
        checkout = Path(output['data']['checkout'])
        # The simulated Reviewer inspects the actual committed file independently.
        correct = (checkout / 'message.txt').read_text() == 'shipped\n'
        self.assertEqual(correct, verdict == 'approve')
        return self.invoke(self.reviewer, verdict, '--answer', 'Yes' if correct else 'No',
                           '--necessary-additions', 'Only the requested file changed.', '--demand-match', 'Scope matches.',
                           '--finding', 'Approved.' if correct else 'Replace almost with shipped.',
                           role='reviewer', task=task, trigger=self.submission_id)

    def test_install_correction_and_integration(self):
        self.install()
        first = self.db()
        self.install()
        repeated = self.db()
        self.assertEqual(len(repeated['agents']), 3)
        self.assertEqual(set(first['agents']), set(repeated['agents']))
        self.assertEqual(set(first['skills']), set(repeated['skills']))
        self.assertEqual(len(repeated['issues']), 1)
        self.assertNotEqual(self.config['developer_id'], self.config['reviewer_id'])
        root = repeated['issues'][self.ids['root']]
        self.assertTrue(root['title'].startswith('MAIN DEV:'))
        self.assertEqual(root['labels'], [{'name': 'manual'}])
        self.assertEqual(root['description'].count('<!-- featssship:installation -->'), 1)
        description = repeated['projects'][self.ids['project']]['description']
        self.assertIn('message.txt', description)
        self.assertIn(self.config['directions'][0]['test_command'], description)
        for package in (self.root_package, self.developer):
            self.call(sys.executable, str(package / 'wrapper.py'), '--validate')
        self.dispatch()
        db = self.db()
        db['runs'] = [{'id': str(uuid.uuid4()), 'issue_id': self.feature_id, 'status': 'running',
                       'agent_id': self.config[role + '_id']} for role in ('reviewer', 'developer')]
        self.db_path.write_text(json.dumps(db))
        first_commit = self.submit('almost')
        posted = next(call for call in reversed(self.db()['calls']) if call[:4] == ['issue', 'comment', 'add', self.feature_id])
        self.assertEqual([posted[i + 1] for i, word in enumerate(posted) if word == '--steer'], [db['runs'][0]['id']])
        compiled = json.loads((self.reviewer / 'review.json').read_text())
        self.assertEqual(compiled['commit'], first_commit)
        self.assertEqual(len(compiled['questions']), 3)
        self.call(sys.executable, str(self.reviewer / 'wrapper.py'), '--validate')
        denied = self.invoke(self.reviewer, role='developer', ok=False)
        self.assertIn('error', denied)
        self.review('rework')
        db = self.db()
        db['runs'] = []
        self.db_path.write_text(json.dumps(db))
        second_commit = self.submit('shipped')
        self.assertNotEqual(first_commit, second_commit)
        self.assertEqual(self.call('git', 'rev-list', '--count', 'origin/main..HEAD').stdout.strip(), '1')
        approved = self.review('approve')
        task, result = self.resume()
        self.assertEqual(result['status'], 'integrate')
        result = self.invoke(self.developer, 'integrate', task=task, trigger=approved['data']['review_id'])
        self.assertEqual(result['status'], 'finished')
        submission = unpack(next(row for row in self.db()['comments'] if row['id'] == self.submission_id)['content'], 'submission')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'shipped\n')
        self.assertEqual(self.db()['issues'][self.feature_id]['status'], 'in_review')
        results = [row for row in self.db()['comments'] if row['issue_id'] == self.ids['root'] and unpack(row['content'], 'result')]
        self.assertEqual(len(results), 1)
        delivered = unpack(results[0]['content'], 'result')
        self.assertEqual(delivered['changes'], submission['changes'])
        self.assertEqual(delivered['summary'], submission['summary'])
        self.assertIn('mention://agent/' + self.ids['main'], results[0]['content'])
        # Model a process ending after publication but before its final status write.
        db = self.db()
        db['issues'][self.feature_id]['status'] = 'in_progress'
        self.db_path.write_text(json.dumps(db))
        task, result = self.resume()
        self.assertEqual(result['status'], 'finished')
        self.assertEqual(self.db()['issues'][self.feature_id]['status'], 'in_review')
        self.assertEqual(len([row for row in self.db()['comments'] if row['issue_id'] == self.ids['root'] and unpack(row['content'], 'result')]), 1)
        evidence = {'fixture': 'simulated native CLI, real Git bare remote and disposable worktrees',
                    'installation_reused': True, 'developer_id': self.config['developer_id'], 'reviewer_id': self.config['reviewer_id'],
                    'correction_commit': first_commit, 'approved_commit': second_commit, 'integration': result['data'],
                    'main_receipt': results[0], 'native_task_ids': sorted({row['source_task_id'] for row in self.db()['comments'] if row.get('source_task_id')})}
        if os.environ.get('FEATSSSHIP_EVIDENCE'):
            Path(os.environ['FEATSSSHIP_EVIDENCE']).write_text(json.dumps(evidence, indent=2))

    def test_manual_hold_and_changed_approval(self):
        self.install()
        self.dispatch()
        commit = self.submit('shipped')
        self.review('approve')
        db = self.db()
        db['issues'][self.feature_id]['labels'] = [{'name': 'manual'}]
        self.db_path.write_text(json.dumps(db))
        task, _ = self.resume()
        held = self.invoke(self.developer, 'integrate', task=task)
        self.assertEqual(held['status'], 'integrate')
        self.assertIn('Manual hold', held['instruction'])
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'baseline\n')
        db = self.db()
        db['comments'].append({'id': str(uuid.uuid4()), 'issue_id': self.feature_id, 'parent_id': self.submission_id,
                               'author_type': 'member', 'author_id': str(uuid.uuid4()), 'content': block('accept', {'commit': commit})})
        self.db_path.write_text(json.dumps(db))
        (self.repo / 'message.txt').write_text('unreviewed\n')
        self.commit('unreviewed')
        local_rejected = self.invoke(self.developer, 'integrate', task=task, ok=False)
        self.assertIn('changed after approval', local_rejected['error']['message'])
        self.call('git', 'push', 'origin', 'HEAD:refs/heads/' + self.binding['branch'])
        rejected = self.invoke(self.developer, 'integrate', task=task, ok=False)
        self.assertIn('error', rejected)
        self.assertIn('changed after approval', rejected['error']['message'])

    def test_linked_worktree_correction_preserves_previous_checkout(self):
        self.install()
        self.dispatch()
        first_commit = self.submit('almost')
        rework = self.review('rework')
        previous = self.repo
        (previous / 'message.txt').write_text('unfinished local edit\n')
        previous_status = self.call('git', 'status', '--porcelain').stdout
        correction = self.base / 'correction'
        self.call('git', 'worktree', 'add', '--detach', str(correction), 'origin/main')
        self.repo = correction
        task = str(uuid.uuid4())
        trigger = rework['data']['review_id']
        self.invoke(self.developer, '--thread', trigger, task=task, trigger=trigger, entry=True)
        self.developer = correction / '.agents/skills/multica-featssship-developer'
        resumed = self.invoke(self.developer, 'resume', task=task, trigger=trigger)
        self.assertEqual(resumed['status'], 'implement')
        self.invoke(self.developer, 'prepare', task=task, trigger=trigger)
        self.assertEqual(self.call('git', 'rev-parse', 'HEAD').stdout.strip(), first_commit)
        self.assertEqual((correction / 'message.txt').read_text(), 'almost\n')
        second_commit = self.submit('shipped', task=task)
        self.assertEqual(self.call('git', 'rev-parse', second_commit + '^').stdout.strip(),
                         self.call('git', 'rev-parse', first_commit + '^').stdout.strip())
        approved = self.review('approve')
        task, resumed = self.resume()
        self.assertEqual(resumed['status'], 'integrate')
        integrated = self.invoke(self.developer, 'integrate', task=task, trigger=approved['data']['review_id'])
        self.assertEqual(integrated['status'], 'finished')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'shipped\n')
        self.assertEqual(self.call('git', 'rev-parse', 'HEAD', cwd=previous).stdout.strip(), first_commit)
        self.assertEqual(self.call('git', 'branch', '--show-current', cwd=previous).stdout.strip(), self.binding['branch'])
        self.assertEqual((previous / 'message.txt').read_text(), 'unfinished local edit\n')
        self.assertEqual(self.call('git', 'status', '--porcelain', cwd=previous).stdout, previous_status)
        results = [row for row in self.db()['comments'] if row['issue_id'] == self.ids['root'] and unpack(row['content'], 'result')]
        self.assertEqual(len(results), 1)

    def test_install_rejects_self_review(self):
        config = json.loads(self.config_path.read_text())
        config.update(developer_id=self.ids['main'], reviewer_id=self.ids['main'])
        self.config_path.write_text(json.dumps(config))
        result = self.call(sys.executable, str(ROOT / 'install.py'), '--config', str(self.config_path), ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.db()['agents']), 1)

    def test_manual_acceptance_uses_native_reply_target(self):
        self.install()
        self.dispatch()
        commit = self.submit('shipped')
        self.review('approve')
        acceptance_id = str(uuid.uuid4())
        db = self.db()
        db['issues'][self.feature_id]['labels'] = [{'name': 'manual'}]
        db['comments'].append({'id': acceptance_id, 'issue_id': self.feature_id, 'parent_id': self.submission_id,
                               'author_type': 'member', 'author_id': str(uuid.uuid4()), 'content': block('accept', {'commit': commit})})
        self.db_path.write_text(json.dumps(db))
        task = str(uuid.uuid4())
        self.invoke(self.developer, '--thread', acceptance_id, task=task, trigger=acceptance_id)
        self.invoke(self.developer, 'resume', task=task, trigger=acceptance_id)
        result = self.invoke(self.developer, 'integrate', task=task, trigger=acceptance_id)
        self.assertEqual(result['status'], 'finished')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'shipped\n')
        self.assertEqual(self.db()['issues'][self.feature_id]['labels'], [{'name': 'manual'}])

    def test_conflict_returns_to_developer_across_tasks(self):
        self.install()
        self.dispatch()
        self.submit('shipped')
        self.review('approve')
        other = self.base / 'other'
        self.call('git', 'clone', str(self.remote), str(other), cwd=self.base)
        (other / 'message.txt').write_text('concurrent main edit\n')
        self.call('git', 'add', 'message.txt', cwd=other)
        self.call('git', 'commit', '-m', 'concurrent main edit', cwd=other)
        self.call('git', 'push', 'origin', 'main', cwd=other)
        task, _ = self.resume()
        result = self.invoke(self.developer, 'integrate', task=task)
        self.assertEqual(result['status'], 'implement')
        _, resumed = self.resume()
        self.assertEqual(resumed['status'], 'implement')
        self.assertEqual(self.call('git', '--git-dir', str(self.remote), 'show', 'main:message.txt').stdout, 'concurrent main edit\n')
        self.assertFalse(any(unpack(row['content'], 'result') for row in self.db()['comments']))


if __name__ == '__main__':
    unittest.main()
