"""Disposable native-CLI fixture; never calls a workspace server."""
import json
import os
from pathlib import Path
import sys
import uuid


def main():
    path = Path(os.environ['FEATSSSHIP_FAKE_DB'])
    db = json.loads(path.read_text())
    args = sys.argv[1:]
    def option(name, default=None):
        return args[args.index('--' + name) + 1] if '--' + name in args else default
    def text(name):
        if '--' + name + '-stdin' in args:
            return sys.stdin.read()
        if option(name + '-file'):
            return Path(option(name + '-file')).read_text()
        return option(name, '')
    def new():
        return str(uuid.uuid4())
    db['calls'].append(args)
    if args[:2] == ['agent', 'get']:
        result = db['agents'][args[2]]
    elif args[:2] == ['agent', 'create']:
        result = {'id': new(), 'name': option('name'), 'runtime_id': option('runtime-id'),
                  'workspace_id': db['workspace_id'], 'instructions': option('instructions'),
                  'model': option('model', ''), 'thinking_level': option('thinking-level', '')}
        db['agents'][result['id']] = result
    elif args[:2] == ['project', 'create']:
        result = {'id': new(), 'workspace_id': db['workspace_id'], 'title': option('title'), 'description': '', 'repository': option('repo')}
        db['projects'][result['id']] = result
    elif args[:2] == ['project', 'get']:
        result = db['projects'][args[2]]
    elif args[:2] == ['project', 'update']:
        result = db['projects'][args[2]]
        result['description'] = option('description')
    elif args[:2] == ['attachment', 'download']:
        row = db['attachments'][args[2]]
        destination = Path(option('output-dir')) / row['filename']
        destination.write_text(row['data'])
        result = {'path': str(destination)}
    elif args[:2] == ['attachment', 'get']:
        result = db['attachments'][args[2]]
    elif args[:2] == ['attachment', 'upload']:
        file = Path(args[2])
        result = {'id': option('attachment-id') or new(), 'filename': file.name, 'data': file.read_text(),
                  'markdown_url': 'http://fixture.invalid/' + file.name, 'created_at': new()}
        db.setdefault('attachments', {})[result['id']] = result
    elif args[:2] == ['issue', 'get']:
        result = db['issues'][args[2]]
    elif args[:2] == ['label', 'list']:
        result = db.setdefault('labels', [{'id': name, 'name': name} for name in ('dev', 'manual')])
    elif args[:2] == ['label', 'create']:
        result = {'id': new(), 'name': option('name')}
        db.setdefault('labels', []).append(result)
    elif args[:3] == ['issue', 'label', 'add']:
        result = db['issues'][args[3]]
        label = next(row for row in db['labels'] if row['id'] == args[4])
        if label not in result['labels']:
            result['labels'].append(label)
    elif args[:2] == ['issue', 'assign']:
        result = db['issues'][args[2]]
        result['assignee_id'] = option('to-id')
    elif args[:3] == ['issue', 'subscriber', 'add']:
        users = db.setdefault('subscribers', {}).setdefault(args[3], [])
        if option('user') not in users:
            users.append(option('user'))
        result = {'ok': True}
    elif args[:2] == ['issue', 'metadata']:
        result = db['issues'][args[3]]
        metadata = result.setdefault('metadata', {})
        if args[2] == 'set':
            metadata[option('key')] = option('value')
        elif args[2] == 'delete':
            metadata.pop(option('key'), None)
        else:
            raise ValueError('Unsupported metadata action')
    elif args[:2] == ['issue', 'create']:
        result = {'id': new(), 'title': option('title'), 'description': text('description'),
                  'project_id': option('project'), 'workspace_id': db['workspace_id'],
                  'parent_issue_id': option('parent'), 'assignee_id': option('assignee-id'),
                  'assignee_type': 'agent', 'labels': [], 'status': option('status'), 'metadata': {}}
        db['issues'][result['id']] = result
    elif args[:2] == ['issue', 'update']:
        result = db['issues'][args[2]]
        if option('project'):
            result['project_id'] = option('project')
        if option('title'):
            result['title'] = option('title')
        if option('status'):
            result['status'] = option('status')
        if '--description-stdin' in args:
            result['description'] = text('description')
    elif args[:2] == ['issue', 'status']:
        result = db['issues'][args[2]]
        result.update(status=args[3], status_category=args[3])
    elif args[:3] == ['issue', 'comment', 'add']:
        parent = option('parent')
        result = {'id': new(), 'issue_id': args[3], 'parent_id': parent, 'content': text('content'), 'revision': 1,
                  'author_type': 'agent', 'author_id': os.environ.get('MULTICA_AGENT_ID'),
                  'source_task_id': os.environ.get('MULTICA_TASK_ID')}
        if option('attachment'):
            file = Path(option('attachment'))
            attachment = {'id': new(), 'filename': file.name, 'data': file.read_text(),
                          'markdown_url': 'http://fixture.invalid/' + file.name,
                          'created_at': str(len(db.setdefault('attachments', {}))).zfill(10)}
            db['attachments'][attachment['id']] = attachment
            result['attachments'] = [attachment]
            db['issues'][args[3]].setdefault('attachments', []).append(attachment)
        db['comments'].append(result)
    elif args[:3] == ['issue', 'comment', 'list']:
        rows = [row for row in db['comments'] if row['issue_id'] == args[3]]
        index = {row['id']: row for row in rows}
        def root(row):
            while row.get('parent_id'):
                row = index[row['parent_id']]
            return row['id']
        if option('thread'):
            target = root(index[option('thread')])
            rows = [row for row in rows if root(row) == target]
            rows = rows[:1] + rows[1:][-int(option('tail', '30')):]
        result = rows
    elif args[:3] == ['issue', 'comment', 'delete']:
        db['comments'] = [row for row in db['comments'] if row['id'] != args[3]]
        result = {'ok': True}
    elif args[:3] == ['issue', 'comment', 'update']:
        result = next(row for row in db['comments'] if row['id'] == args[3])
        if str(result['revision']) != option('expected-revision'):
            raise ValueError('Comment revision mismatch')
        result['content'] = text('content')
        result['revision'] += 1
    else:
        raise ValueError('Unsupported CLI call: ' + str(args))
    path.write_text(json.dumps(db))
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
