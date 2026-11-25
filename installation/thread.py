"""Native same-thread posting shared by installation, delegation and dev-rev."""
import json
from pathlib import Path
import tempfile

from featssship import cli, mention


def reply_parent(context):
    state = context['state']
    if context['native_issue_id'] == context['issue_id']:
        if parent := getattr(context['args'], 'thread', None) or context['native_comment_id']:
            state['reply_parent'] = parent
    return state.get('reply_parent')


def post(context, content, *, attachment=None):
    parent = reply_parent(context)
    if not parent and context['native_issue_id'] != context['issue_id']:
        raise ValueError('No saved reply thread on the SoP owner issue.')
    words = ['issue', 'comment', 'add', context['issue_id'], '--content-stdin']
    if parent:
        words += ['--parent', parent]
    if attachment:
        words += ['--attachment', str(attachment)]
    return cli(*words, input=content)


def wake_callback(context, agent_id, message):
    return post(context, mention(agent_id) + ' ' + message + '\n\nResume the current SoP.')


def write_config(context, reference, config, message=' '):
    # TODO: Replace immutable attachment revisions with native deliverable update.
    with tempfile.TemporaryDirectory(prefix='.featssship-', dir=Path.cwd()) as directory:
        path = Path(directory) / reference['filename']
        path.write_text(json.dumps(config, indent=2) + '\n')
        return post(context, message, attachment=path)
