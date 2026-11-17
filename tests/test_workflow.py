import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
MULTICA = shutil.which('multica')
sys.path.insert(0, str(ROOT / 'installation'))
from featssship import CONFIG_KEY, DELEGATION_KEY, DISPATCH_KEY, config_ref, feature_branch, request_config


class BranchNamingTests(unittest.TestCase):
    def test_direction_developer_precedence(self):
        installed = {'installed_developer_id': 'global', 'directions': [
            {'name': 'frontend', 'developer_id': 'direction'}, {'name': 'backend'}]}
        for item, developer in (
            ({'direction': 'frontend'}, 'direction'),
            ({'direction': 'backend'}, 'global'),
            ({'direction': 'frontend', 'developer_id': 'explicit'}, 'explicit'),
        ):
            with self.subTest(item=item):
                self.assertEqual(request_config({'issues': [item]}, installed, index=0)['developer_id'], developer)

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
        self.env.pop('MULTICA_COMMENT_ID', None)
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
        trigger = str(uuid.uuid4())
        db['comments'].append({'id': trigger, 'issue_id': self.ids['installer'], 'parent_id': None,
                               'content': 'Fixture installation request', 'author_type': 'member', 'revision': 1})
        self.env['MULTICA_COMMENT_ID'] = trigger
        self.db_path.write_text(json.dumps(db))
        fixture = self
        class NativeTransport(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                url = urlsplit(self.path)
                if url.path.startswith('/api/workspaces/'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"slug":"fixture"}')
                    return
                if not (url.path.startswith('/api/issues/') and url.path.endswith('/comments')):
                    self.send_error(404)
                    return
                rows = [row for row in fixture.db()['comments'] if row['issue_id'] == url.path.split('/')[3]]
                thread = parse_qs(url.query).get('thread', [None])[0]
                if thread:
                    index = {row['id']: row for row in rows}
                    def root(row):
                        while row.get('parent_id'):
                            row = index[row['parent_id']]
                        return row['id']
                    rows = [row for row in rows if root(row) == root(index[thread])]
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(rows).encode())
            def do_POST(self):
                if not (self.path.startswith('/api/issues/') and self.path.endswith('/comments')):
                    self.send_error(404)
                    return
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                db = fixture.db()
                row = {'id': str(uuid.uuid4()), 'issue_id': self.path.split('/')[3], 'revision': 1, **data}
                db['comments'].append(row)
                fixture.db_path.write_text(json.dumps(db))
                self.send_response(201)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(row).encode())
        server = HTTPServer(('127.0.0.1', 0), NativeTransport)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.env.update(MULTICA_SERVER_URL='http://127.0.0.1:' + str(server.server_port), MULTICA_TOKEN='fixture')
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

    def install(self):
        if self.installer()['status'] != 'finished':
            self.installer('publish', '--patch', '{}')
            self.assertEqual(self.installer('confirm')['status'], 'finished')

    def test_split_questionnaire_uses_child_threads_and_direction_developer(self):
        config = self.read_answers()
        direction_developer = str(uuid.uuid4())
        config['develop_reviewer_split'] = True
        config['directions'][0].update(developer_id=direction_developer, test_command='evaluate.py')
        self.write_answers(config)
        db = self.db()
        db['agents'][direction_developer] = {'id': direction_developer, 'name': 'Direction Developer',
            'runtime_id': self.ids['runtime'], 'workspace_id': self.ids['workspace']}
        self.db_path.write_text(json.dumps(db))
        self.install()
        db = self.db()
        main = next(row for row in db['issues'].values() if row['title'].startswith('MAIN DEV:'))
        reviewer_id = config_ref(db['issues'][self.ids['installer']])['installed_reviewer_id']
        thread = str(uuid.uuid4())
        db['comments'].append({'id': thread, 'issue_id': main['id'], 'parent_id': None,
                               'content': 'Experiment request', 'revision': 1})
        self.db_path.write_text(json.dumps(db))
        name = 'multica-featssship-' + self.ids['project'][:8]
        env = {**self.env, 'MULTICA_ISSUE_ID': main['id'], 'MULTICA_AGENT_ID': main['assignee_id'],
               'MULTICA_WORKSPACE_ID': self.ids['workspace'], 'MULTICA_COMMENT_ID': thread}
        self.call(MULTICA, 'sop', 'run', name, '--thread', thread, '--config',
                  json.dumps({'issues': [{'name': 'variant', 'request': 'Develop a variant.'}]}), env=env)
        state = json.loads(self.db()['issues'][main['id']]['metadata']['sop.' + name])
        self.call(MULTICA, 'sop', 'run', name, 'refresh', '--config-file', state['draft']['path'], env=env)
        self.call(MULTICA, 'sop', 'run', name, 'confirm', env=env)
        db = self.db()
        review = next(row for row in db['issues'].values() if row.get('parent_issue_id') == main['id'])
        review_thread = next(row['id'] for row in db['comments'] if row['issue_id'] == review['id'])
        env.update(MULTICA_ISSUE_ID=review['id'], MULTICA_AGENT_ID=reviewer_id, MULTICA_COMMENT_ID='')
        skill = 'multica-featssship-devrev-split'
        self.call(MULTICA, 'sop', 'run', skill, '--thread', review_thread, env=env)
        self.call(MULTICA, 'sop', 'run', skill, 'prepare', env=env)
        db = self.db()
        developer = next(row for row in db['issues'].values() if row.get('parent_issue_id') == review['id'])
        state = json.loads(db['issues'][review['id']]['metadata']['sop.' + skill])
        self.assertEqual(developer['assignee_id'], direction_developer)
        self.assertEqual(state['owner']['issue_id'], developer['id'])
        self.assertEqual(state['owner']['thread'], state['developer_thread'])
        forwarded = next(row for row in db['comments'] if row['id'] == state['questionnaire']['forwarded_comment_id'])
        self.assertEqual(forwarded['parent_id'], state['developer_thread'])
        self.assertTrue(any(call[:2] == ['attachment', 'upload'] and '--independent' in call
                            and call[2].endswith('multica-featssship-devrev-split-state.html')
                            for call in db['calls']))
        tree = Path(state['worktree'])
        image, answer = str(uuid.uuid4()), str(uuid.uuid4())
        db['attachments'][image] = {'id': image, 'content_type': 'image/png', 'markdown_url': '/image',
                                    'issue_id': developer['id']}
        db['comments'].append({'id': answer, 'issue_id': developer['id'], 'parent_id': forwarded['id'],
                               'content': 'Candidate ready', 'revision': 1})
        self.db_path.write_text(json.dumps(db))
        env.update(MULTICA_ISSUE_ID=developer['id'], MULTICA_COMMENT_ID=answer)
        def candidate(commit, pipeline, *, ok=True):
            return self.call(MULTICA, 'sop', 'run', skill, 'candidate_ready', '--issue', review['id'],
                             '--commit', commit, '--summary', 'Variant', '--pipeline', pipeline,
                             '--visual-attachment', image, env=env, ok=ok)
        base = self.call('git', 'rev-parse', 'HEAD', cwd=tree).stdout.strip()
        self.assertIn('actual changes', json.loads(candidate(base, 'message.txt', ok=False).stdout)['error']['message'])
        self.call('git', 'commit', '--allow-empty', '-m', 'Empty experiment', cwd=tree)
        empty = self.call('git', 'rev-parse', 'HEAD', cwd=tree).stdout.strip()
        self.assertIn('actual changes', json.loads(candidate(empty, 'message.txt', ok=False).stdout)['error']['message'])
        (tree / 'pipeline.txt').write_text('source -> output\n')
        self.call('git', 'add', 'pipeline.txt', cwd=tree)
        self.call('git', 'commit', '-m', 'Experiment pipeline', cwd=tree)
        commit = self.call('git', 'rev-parse', 'HEAD', cwd=tree).stdout.strip()
        db = self.db()
        db['attachments'][image]['issue_id'] = str(uuid.uuid4())
        self.db_path.write_text(json.dumps(db))
        self.assertIn('Developer issue', json.loads(candidate(commit, 'pipeline.txt', ok=False).stdout)['error']['message'])
        db = self.db()
        db['issues'][developer['id']]['metadata']['independent_artifacts'] = json.dumps([image])
        self.db_path.write_text(json.dumps(db))
        candidate(commit, 'pipeline.txt')
        db = self.db()
        wake = next(row for row in db['comments'] if row['issue_id'] == review['id'] and 'Candidate ready:' in row['content'])
        self.assertEqual(wake['parent_id'], review_thread)
        self.assertEqual(json.loads(db['issues'][review['id']]['metadata']['sop.' + skill])['status'], 'review')

    def test_dispatch_completion_help_and_reentry(self):
        from packages import build
        name = 'multica-featssship'
        skills = self.repo / '.agents/skills'
        build('delegation', skills / name)
        build('feature', skills / 'multica-featssship-develop-review')
        (skills / name / 'config.json').unlink()
        config = self.read_answers()
        config.update(manual=True, installed_developer_id=str(uuid.uuid4()),
                      installed_reviewer_id=str(uuid.uuid4()))
        self.write_answers(config)
        db = self.db()
        main = db['issues'][self.ids['installer']]
        thread, child_id = str(uuid.uuid4()), str(uuid.uuid4())
        reference = {'issue_id': main['id'], 'filename': 'batch.json'}
        batch = {'issues': [{'name': 'callback', 'request': 'Ship callback fix.'},
                            {'name': 'retry', 'request': 'Ship retry fix.'}],
                 'source': config_ref(main), 'main_issue_id': main['id'], 'dispatch_thread': thread}
        row = {'id': str(uuid.uuid4()), 'filename': reference['filename'], 'data': json.dumps(batch)}
        db['attachments'][row['id']] = row
        main['attachments'].append(row)
        main['metadata'][DELEGATION_KEY] = json.dumps(reference)
        main['metadata'][DISPATCH_KEY] = json.dumps({'thread': thread, 'draft_attachment_id': row['id'],
                                                   'items': [{'issue_id': child_id}, {}]})
        task = self.base / 'main-task'
        task.mkdir()
        main['metadata']['sop.' + name] = json.dumps({'status': 'outer_decide', 'workdir': str(task)})
        db['issues'][child_id] = {'id': child_id, 'status': 'backlog', 'labels': [], 'metadata': {}}
        self.db_path.write_text(json.dumps(db))
        env = {**self.env, 'MULTICA_ISSUE_ID': main['id'], 'MULTICA_AGENT_ID': self.ids['main'],
               'MULTICA_WORKSPACE_ID': self.ids['workspace'], 'MULTICA_SOP_SKILL_ROOTS': str(skills)}
        self.call('git', 'branch', 'feat/messages/retry')
        result = self.call(MULTICA, 'sop', 'run', name, 'confirm', cwd=task, env=env, ok=False)
        self.assertIn('already claimed', result.stdout, result.stderr)
        first_child = self.db()['issues'][child_id]
        self.assertEqual(first_child['status'], 'todo')
        self.call('git', 'branch', '-m', 'feat/messages/retry', 'fixture-claimed')
        result = self.call(MULTICA, 'sop', 'run', name, 'confirm', cwd=task, env=env)
        self.assertEqual(json.loads(result.stdout)['status'], 'FINISHED')
        child = self.db()['issues'][child_id]
        self.assertEqual(child['status'], 'todo')
        self.assertEqual({label['name'] for label in child['labels']}, {'dev', 'manual'})
        worktree = self.repo / '.git/featsship' / child_id
        self.assertEqual(self.call('git', 'branch', '--show-current', cwd=worktree).stdout.strip(),
                         'feat/messages/callback')
        metadata = self.db()['issues'][main['id']]['metadata']
        self.assertNotIn(DISPATCH_KEY, metadata)
        self.assertNotIn('sop.' + name, metadata)
        self.assertEqual(config_ref(child, DELEGATION_KEY), {**reference, 'index': 0})
        self.assertEqual(self.document(child, DELEGATION_KEY), batch)
        self.assertEqual(sum(call[:2] == ['issue', 'create'] for call in self.db()['calls']), 1)

        db = self.db()
        db['issues'][main['id']]['metadata'][DISPATCH_KEY] = json.dumps(
            {'thread': thread, 'draft_attachment_id': row['id'], 'items': [{'issue_id': child_id, 'dispatched': True}]})
        self.db_path.write_text(json.dumps(db))
        metadata = db['issues'][main['id']]['metadata']
        help_text = self.call(MULTICA, 'sop', 'run', name, '--help', cwd=task, env=env).stdout
        self.assertEqual(help_text.strip(), (skills / name / 'SKILL.md').read_text().split('---', 2)[2].strip())
        self.assertEqual(self.db()['issues'][main['id']]['metadata'], metadata)
        new_thread = str(uuid.uuid4())
        failed = self.call(MULTICA, 'sop', 'run', name, '--thread', new_thread, '--config', '{}', cwd=task, env=env, ok=False)
        self.assertIn('error', json.loads(failed.stdout))
        self.assertNotIn('sop.' + name, self.db()['issues'][main['id']]['metadata'])
        result = self.call(MULTICA, 'sop', 'run', name, '--thread', new_thread, cwd=task, env=env)
        self.assertEqual(json.loads(result.stdout)['status'], 'edit')
        state = json.loads(self.db()['issues'][main['id']]['metadata']['sop.' + name])
        draft = json.loads(Path(state['draft']['path']).read_text())
        self.assertEqual(draft['issues'], [{'direction': 'message'}])
        self.assertEqual(draft['dispatch_thread'], new_thread)
        self.assertNotEqual(state['draft']['reference'], reference)
        self.assertEqual(self.document(child, DELEGATION_KEY), batch)

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


if __name__ == '__main__':
    unittest.main()
