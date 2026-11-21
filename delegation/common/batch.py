"""MAIN drafts a batch; outer confirms dispatch or requests changes."""
import json
from pathlib import Path
import uuid
import tempfile

from featssship import DELEGATION_KEY, DISPATCH_KEY, attachment, check_repo, cli, config_ref, delegation_config, download_config, entry_command, git, has_manual, link_config, read_config, request_config

from thread import reply_parent, wake_callback, write_config

SOP_DISPLAY_NAME = 'multica-featssship-delegation'

FIELDS = {**dict.fromkeys(('name', 'request', 'direction', 'title', 'scope', 'github_issue', 'branch', 'parent_branch', 'developer_id'), str),
          'manual': bool, 'sandbox': dict, 'questions': list}
DRAFT_PROMPT = ('Read the batch JSON at <file path>, apply the request offline, then publish '
          'with refresh --config-file PATH.')
OUTER_PROMPT = 'Confirm or edit.'
REPLY_GUIDANCE = 'Briefly explain the batch changes in this thread, then end this turn.'


def save_progress(context):
    cli('issue', 'metadata', 'set', context['issue_id'], '--key', DISPATCH_KEY,
        '--value', json.dumps(context['record']), '--type', 'string')


def batch_config(batch, context):
    envelope = {'source': config_ref(context['main']), 'main_issue_id': context['issue_id'],
                'dispatch_thread': context['record']['thread']}
    if (not isinstance(batch, dict) or set(batch) - {'issues', *envelope}
            or not isinstance(batch.get('issues'), list) or not batch['issues']
            or any(key in batch and batch[key] != value for key, value in envelope.items())):
        raise ValueError('Use {"issues": [{...}]} and keep source/owner/thread references unchanged.')
    if any(not isinstance(item, dict) or set(item) - set(FIELDS)
           or any(not isinstance(value, FIELDS[key]) for key, value in item.items()) for item in batch['issues']):
        raise ValueError('Each issues item accepts typed request fields: ' + ', '.join(FIELDS))
    return delegation_config(context['installed'], batch, **envelope)


def publish(batch, context):
    config = batch_config(batch, context)
    write_config(context, context['reference'], config)
    link_config(context['issue_id'], context['reference'], DELEGATION_KEY)
    context['record'] = {'thread': config['dispatch_thread'],
                         'draft_attachment_id': attachment(context['reference'])['id']}
    save_progress(context)


def configured(context):
    main, args = cli('issue', 'get', context['issue_id']), context['args']
    source = config_ref(main)
    if not source or main['workspace_id'] != context['workspace_id'] or main['assignee_id'] != context['agent_id']:
        raise context['error']('wrong_agent', 'Use the configured MAIN and its native assignee.')
    context.update(main=main, reference=config_ref(main, DELEGATION_KEY),
                   record=json.loads(main.get('metadata', {}).get(DISPATCH_KEY, '{}')))
    state = context['state']
    context['installed'] = read_config(source)
    if not state.get('status'):
        context['record'] = {}
    if (args.config is not None or not context['record']) and not state.get('draft'):
        if context['record']:
            raise ValueError('Use refresh to edit the current batch.')
        if not args.thread:
            raise ValueError('Start with --thread <original MAIN request comment>.')
        batch = json.loads(args.config) if args.config is not None else {'issues': [{}]}
        context.update(record={'thread': args.thread}, reference={
            'issue_id': main['id'], 'filename': 'featssship.delegation-' + str(uuid.uuid4()) + '.json'})
        path = Path(tempfile.mkdtemp(prefix='featssship-delegation-')) / context['reference']['filename']
        path.write_text(json.dumps(batch_config(batch, context), indent=2) + '\n')
        state['draft'] = {'thread': args.thread, 'reference': context['reference'], 'path': str(path)}
        args.config, context['argv'] = None, []
    if draft := state.get('draft'):
        context.update(record={'thread': draft['thread']}, reference=draft['reference'])
        path = Path(draft['path'])
    else:
        path = download_config(context['reference'], tempfile.mkdtemp(prefix='featssship-delegation-'))
        context['revision'] = attachment(context['reference'])['id']
    context.update(config=json.loads(path.read_text()), config_path=str(path))


def view(context):
    return {'instruction': DRAFT_PROMPT.replace('<file path>', context['config_path']) +
            ('\n\nRequested changes: ' + context['state']['change_request']
             if context['state'].get('change_request') else '')}


def outer_owner(context):
    return {'issue_id': context['issue_id'], 'thread': reply_parent(context),
            'id': None, 'content': '/note'}


def outer_view(context):
    row = attachment(context['reference'])
    return {'instruction': OUTER_PROMPT + '\n\n[' + row['filename'] + '](' + row['markdown_url'] + ').'}


def request_changes(args, context):
    if any(item.get('issue_id') for item in context['record'].get('items', [])):
        raise ValueError('Children exist; resume dispatch instead of editing this batch.')
    context['state']['change_request'] = args.change_request
    wake_callback(context, context['main']['assignee_id'], 'Batch changes requested: ' + args.change_request)


def refresh(args, context):
    """```dot
    digraph refresh { node [shape=box]; read [label="Read offline JSON and validate issues"];
        upload [label="Publish batch attachment"]; read -> upload; }
    ```"""
    if any(item.get('issue_id') for item in context['record'].get('items', [])):
        raise ValueError('Children exist; resume dispatch instead of refreshing this batch.')
    publish(json.loads(Path(args.config_file).read_text()), context)
    context['state'].pop('draft', None)
    context['state'].pop('change_request', None)
    context['argv'] = []
    configured(context)
    return {'this_round_reply_guidance': REPLY_GUIDANCE}
