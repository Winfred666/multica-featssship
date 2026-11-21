"""Native same-thread posting shared by installation, delegation and dev-rev."""
import json
from pathlib import Path
import tempfile

from featssship import cli, mention


def reply_parent(context):
    state = context['state']
    if context['native_issue_id'] == context['issue_id'] and context['native_comment_id']:
        state['reply_parent'] = context['native_comment_id']
    elif getattr(context['args'], 'thread', None):
        state['reply_parent'] = context['args'].thread
    return state.get('reply_parent')


def check_callback_thread(context):
    if context['native_comment_id'] and context['native_issue_id'] != context['issue_id']:
        # //TODO: wait stage 3.5 backend and cli endpoint simplification to post comment by default in same thread.
        raise ValueError('Cannot post a callback to the SoP owner issue in the triggering display issue thread.')


def post(context, content, *, attachment=None, steer=False):
    check_callback_thread(context)
    words = ['issue', 'comment', 'add', context['issue_id'], '--content-stdin']
    if parent := reply_parent(context):
        words += ['--parent', parent]
    if attachment:
        words += ['--attachment', str(attachment)]
    if steer:
        words += ['--steer-active']
    return cli(*words, input=content)


def wake_callback(context, agent_id, message):
    return post(context, mention(agent_id) + ' ' + message + '\n\nResume the current SoP.', steer=True)


def write_config(context, reference, config, message=' '):
    # TODO: Replace immutable attachment revisions with native deliverable update.
    with tempfile.TemporaryDirectory(prefix='.featssship-', dir=Path.cwd()) as directory:
        path = Path(directory) / reference['filename']
        path.write_text(json.dumps(config, indent=2) + '\n')
        return post(context, message, attachment=path)
