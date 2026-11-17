"""Canonical score adapter. Private inputs are local to a dedicated Reviewer UID."""
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from featssship import cli

POLICIES = Path('/etc/multica-featssship/split')


def private_evaluator(binding):
    # Runtime IDs alone are not isolation. An operator binds runtime accounts to
    # distinct Unix UIDs in a root-owned policy, outside all issue attachments.
    if os.name != 'posix' or not hasattr(os, 'getuid'):
        raise ValueError('Private evaluation requires dedicated Unix runtime accounts.')
    if binding['test_command'] != 'evaluate.py':
        raise ValueError('Split direction test_command must name the canonical evaluate.py script.')
    for path in (POLICIES.parent, POLICIES, POLICIES / (binding['reviewer_id'] + '.json')):
        info = path.stat()
        if info.st_uid != 0 or info.st_mode & 0o022 or path.is_symlink():
            raise ValueError('Evaluation policy must be root-owned and not group/world writable.')
    policy = json.loads(path.read_text())
    uid = os.getuid()
    if (uid == 0 or policy['reviewer_uid'] != uid or policy['developer_uid'] in (0, uid)
            or policy['developer_id'] != binding['developer_id']):
        raise ValueError('Reviewer and Developer require distinct, unprivileged Unix accounts.')
    for role in ('reviewer', 'developer'):
        agent = cli('agent', 'get', binding[role + '_id'])
        if agent['runtime_id'] != policy[role + '_runtime_id']:
            raise ValueError('Runtime/account policy no longer matches the selected agents.')
    if policy['reviewer_runtime_id'] == policy['developer_runtime_id']:
        raise ValueError('One shared runtime cannot provide the required Unix account boundary.')
    directory = Path(policy['evaluators'][binding['direction']]).resolve()
    info = directory.stat()
    if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Private evaluator directory must be owned by Reviewer with mode 0700.')
    script = directory / 'evaluate.py'
    info = script.stat()
    if script.is_symlink() or info.st_uid != uid or info.st_mode & 0o022:
        raise ValueError('Private evaluate.py must be Reviewer-owned and not group/world writable.')
    return script


def numeric_score(output):
    result = json.loads(output)
    value = result.get('score') if isinstance(result, dict) else None
    if (not isinstance(result, dict) or set(result) != {'score'} or type(value) not in (int, float)
            or not math.isfinite(value)):
        raise ValueError('Canonical evaluator must return only {"score": <finite number>}.')
    return value


def evaluate(context):
    state, binding = context['state'], context['binding']
    if state.get('evaluation_attempted'):
        raise ValueError('Evaluation already attempted. No rerun is permitted; no score is invented after failure.')
    try:
        script = private_evaluator(binding)
    except (OSError, KeyError, ValueError):
        raise ValueError('Private evaluation unavailable. Supply the canonical evaluate.py, real hidden inputs and '
                         'root-owned runtime/Unix-account policy. See docs/workflow.md#private-evaluation-boundary.') from None
    # Export exactly the submitted object, not the mutable Developer worktree.
    with tempfile.TemporaryDirectory(prefix='candidate-', dir=script.parent) as temporary:
        candidate = Path(temporary) / 'candidate.tar'
        with candidate.open('wb') as output:
            subprocess.run(['git', '-C', state['worktree'], 'archive', '--format=tar', state['commit']],
                           stdout=output, stderr=subprocess.DEVNULL, check=True)
        state['evaluation_attempted'] = True
        context['save_state']()
        # Trusted evaluator owns any execution sandbox for candidate code. Never
        # execute candidate code with Reviewer privileges or hidden files mounted.
        result = subprocess.run(['python3', str(script), '--candidate', str(candidate)],
                                cwd=script.parent, text=True, capture_output=True)
        if result.returncode:
            raise ValueError('Canonical evaluation failed. Private stdout/stderr withheld; no rerun permitted.')
        try:
            state['score'] = numeric_score(result.stdout)
        except (ValueError, OverflowError):
            raise ValueError('Canonical evaluation returned invalid score JSON. Private output withheld; no rerun permitted.') from None
        context['save_state']()
