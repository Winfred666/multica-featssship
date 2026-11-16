"""Develop and review in the issue's shared folder and branch; report to MAIN."""
from pathlib import Path
import os
import json

from featssship import check_repo, clean, cli, comment, feature_config, git, run, test
from sop import Branch, Completed, Option, Parameter, State, Workflow

CACHE_VIEW = False
FINAL_DONE = 'directly and silently end this turn'

REVIEW_PROMPT = ('Reviewer: inspect the submitted diff in this issue\'s shared folder and branch '
                 'without source edits or tests. '
                 'Answer the selected review questions in --finding. Approve or return corrections.')

INTEGRATION_PROMPT = ('Reviewer: quickly judge and recover this integration/publication failure. '
                      'Preserve interrupted Git/rebase state; do not abort or restart it blindly. '
                      'Repair within existing authorization without editing tracked product code or bypassing required checks. '
                      'Hash changes from a clean rebase alone do not require source rework. '
                      'Choose rework only when Developer corrections are needed; retain submission, review and any required outer approval.')


def owner(role):
    return lambda context: cli('agent', 'get', context['binding'][role + '_id'])


def outer_owner(context):
    binding = context['binding']
    return {'issue_id': binding['main_issue_id'], 'thread': binding['dispatch_thread'],
            'id': None, 'content': 'Review passed. Approve integration or return corrections to Developer.'}


def handoff_guidance(context, role, message):
    recipient, state = owner(role)(context), context['state']
    return ('Post the following handoff with `multica issue comment add ' + context['issue_id'] +
            ' --content-file <file>` in the current thread; do not put it only in the final response. '
            'Use the facts and links below without retrieving them again. '
            'Fill only <brief explanation> from the actual feature context, not file sizes. '
            'Then directly and silently end this turn; do not run the receiving role’s callback.\n\n'
            f'[@{recipient["name"]}](mention://agent/{recipient["id"]}) {message}\n\n'
            'Impact: <brief explanation>\n\n'
            f'Submitted revision: {state["feature"]}\n\n{state["diff"]}')


def review_view(context):
    return {'instruction': REVIEW_PROMPT +
            '\n\nReview questions:\n' + '\n'.join('- ' + q for q in context['binding']['questions'])}


def integration_view(context):
    return {'instruction': INTEGRATION_PROMPT + '\n\n' + context['state']['integration_error']}


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    context.update(issue=issue, binding=feature_config(issue))
    if issue['status'] == 'cancelled' or (issue['status'] == 'done' and context['phase'] not in ('done', 'amending')):
        raise Completed(FINAL_DONE, target=Workflow.FINISHED)


def enter_develop(context):
    """Initial entry runs after the runtime's state-owner check."""
    if not context['state'].get('status'):
        cli('issue', 'status', context['issue_id'], 'in_progress')
    return {}


def shared_repo(context):
    repo = Path.cwd()
    clean(repo)
    check_repo(repo, context['binding'])
    branch = git(repo, 'branch', '--show-current')
    if branch != context['binding']['branch']:
        raise ValueError('Use the one feature branch selected by MAIN in this issue folder.')
    return repo


def checkout(context, common, commit):
    repo = common / 'featsship' / context['issue_id']
    git(common, 'worktree', 'add', '-b', context['binding']['branch'], str(repo), commit)
    os.chdir(repo)


def feature_link(repo, binding, commit):
    remote = binding['repository'].removesuffix('.git').replace('git@github.com:', 'https://github.com/').rstrip('/')
    return f'[{git(repo, "log", "-1", "--format=%s", commit)}]({remote}/commit/{commit})'


def submit(args, context):
    """```dot
    digraph submit { node [shape=box]; check [label="Verify repository, MAIN branch and one feature commit"];
        push [label="Test; push only if manual; request Reviewer"]; check -> push; }
    ```"""
    repo, binding = shared_repo(context), context['binding']
    git(repo, 'fetch', 'origin', binding['parent_branch'])
    revisions = 'origin/' + binding['parent_branch'] + '..HEAD'
    if git(repo, 'rev-list', '--count', revisions) != '1' or git(repo, 'rev-list', '--merges', revisions):
        raise ValueError('Keep one feature commit; amend corrections. Do not create merge commits.')
    test(repo, binding['test_command'])
    ref = 'refs/heads/' + binding['branch']
    if binding['manual']:
        git(repo, 'push', '--force-with-lease=' + ref + ':' + context['state'].get('commit', context['issue']['metadata'].get('git_base_commit', '')), 'origin', 'HEAD:' + ref)
    feature = git(repo, 'rev-parse', 'HEAD')
    context['state'].pop('integrated', None)
    context['state'].update(commit=feature,
                            feature=feature_link(repo, binding, feature), diff=diff_report(repo, binding))
    cli('issue', 'status', context['issue_id'], 'in_review')
    return {'this_round_reply_guidance': handoff_guidance(context, 'reviewer',
            args.summary + '\n\nVerified: `' + binding['test_command'] + '` passed.')}


def diff_report(repo, binding):
    rows = [line.split('\t', 2) for line in git(repo, 'diff', '--numstat',
            'origin/' + binding['parent_branch'] + '...HEAD').splitlines()]
    sizes = [(int(added) if added != '-' else 0, int(deleted) if deleted != '-' else 0, path)
             for added, deleted, path in rows]
    totals = f'+{sum(a for a, _, _ in sizes)} / -{sum(d for _, d, _ in sizes)} lines across {len(rows)} files'
    remote = binding['repository'].removesuffix('.git').replace('git@github.com:', 'https://github.com/').rstrip('/')
    base = git(repo, 'merge-base', 'origin/' + binding['parent_branch'], 'HEAD')
    head = git(repo, 'rev-parse', 'HEAD')
    totals += f' · [Full diff]({remote}/compare/{base}...{head})'
    table = ['Largest file deltas (size only, not a complete feature explanation):',
             '', '| File | Added / deleted |', '| --- | --- |']
    table += [f'| `{path}` | +{added} / -{deleted} |'
              for added, deleted, path in sorted(sizes, key=lambda row: row[0] + row[1], reverse=True)[:3]]
    return totals + ('\n\n' + '\n'.join(table) if rows else '')


def final_note(context):
    state, binding = context['state'], context['binding']
    if state.get('cancel_reason'):
        return '/note sub-issue CANCELLED: ' + state['cancel_reason']
    note = '/note sub-issue DONE: ' + state['feature'] + '.'
    source = binding.get('github_issue')
    if source:
        issue = json.loads(run('gh', 'issue', 'view', source, '--json', 'state,title,url'))
        if issue['state'] == 'CLOSED':
            note += f" GitHub issue [{issue['title']}]({issue['url']}) solved and closed."
    return note + '\n\n' + state['diff']


def authorize_amendment(args, context):
    if not args.thread:
        raise ValueError('Amend only on an explicit outer request; pass its comment UUID with --thread.')
    rows = cli('issue', 'comment', 'list', context['issue_id'], '--thread', args.thread, '--tail', '30')
    outer = next((row for row in rows if row['id'] == args.thread), None)
    if not outer or not (outer.get('author_type') == 'member' or outer.get('author_id') == context['binding']['delegator_id']):
        raise ValueError('Amend only on an explicit outer request; pass the superior instruction with --thread.')


def verdict(args, context):
    """```dot
    digraph verdict { node [shape=box]; inspect [label="Read submitted revision"];
        rework [label="Return corrections to Developer"];
        approve [label="Approve; Reviewer owns integration"];
        inspect -> rework [label="rework"]; inspect -> approve [label="approve"]; }
    ```"""
    if args.event == 'cancel':
        context['state']['cancel_reason'] = args.reason
        return finish(context)
    binding, state = context['binding'], context['state']
    if not (context['phase'] in ('manual_approve', 'integration_error') and args.event == 'rework') and git(shared_repo(context), 'rev-parse', 'HEAD') != state['commit']:
        raise ValueError('Review the exact submitted revision; changed code needs a new submission.')
    if args.event == 'approve' and context['phase'] == 'review' and binding['manual']:
        return {'this_round_reply_guidance': 'Briefly explain the reviewed changes. '
                'The approval questionnaire goes to MAIN’s delegator; end this turn.'}
    if args.event == 'rework':
        if context['phase'] == 'integration_error':
            state.pop('integration_error', None)
        cli('issue', 'status', context['issue_id'], 'in_progress')
        return {'this_round_reply_guidance': handoff_guidance(context, 'developer', args.finding)}
    return {}


def retained_rebase(repo):
    return next((repo / git(repo, 'rev-parse', '--git-path', name)
                 for name in ('rebase-merge', 'rebase-apply')
                 if (repo / git(repo, 'rev-parse', '--git-path', name)).is_dir()), None)


def merge_approved(args, context):
    """```dot
    digraph merge_approved { node [shape=box]; check [label="Reviewer: verify approved HEAD"];
        rebase [label="Rebase feature onto latest main; continue retained rebase"];
        finish [label="Test, advance main, clean up and push"];
        judge [label="Reviewer: quick-judge integration error"];
        check -> rebase -> finish;
        rebase -> judge [label="error"]; finish -> judge [label="error"]; }
    ```"""
    repo, binding, state = Path.cwd(), context['binding'], context['state']
    commit = state.get('integrated', state['commit'])
    try:
        check_repo(repo, binding)
        rebase = retained_rebase(repo)
        if rebase:
            if ((rebase / 'orig-head').read_text().strip() != commit or
                    (rebase / 'head-name').read_text().strip() != 'refs/heads/' + binding['branch']):
                raise ValueError('The retained rebase does not belong to the approved revision and MAIN branch. Preserve it for Reviewer judgment.')
        else:
            shared_repo(context)
            if git(repo, 'rev-parse', 'HEAD') != commit:
                raise ValueError('Integrate the exact approved revision; changed code needs a new review.')
            test(repo, binding['test_command'])
        if binding['manual'] and git(repo, 'ls-remote', 'origin', 'refs/heads/' + binding['branch']).split()[0] != state['commit']:
            raise ValueError('The remote feature branch changed after submission.')
        if rebase:
            git(repo, 'rebase', '--continue')
        else:
            git(repo, 'fetch', 'origin', binding['parent_branch'])
            upstream = git(repo, 'rev-parse', 'origin/' + binding['parent_branch'])
            git(repo, 'rebase', upstream)
        commit = git(repo, 'rev-parse', 'HEAD')
        state.update(integrated=commit, feature=feature_link(repo, binding, commit), diff=diff_report(repo, binding))
        test(repo, binding['test_command'])
        advance_parent(repo, binding, commit)
        state.pop('integration_error', None)
    except ValueError as error:
        state['integration_error'] = 'Integration stopped: ' + str(error)
        return {'phase': 'integration_error'}
    return finish(context)


def advance_parent(repo, binding, integrated, previous=None):
    ref = 'refs/heads/' + binding['parent_branch']
    parents = [block.splitlines()[0][9:] for block in git(repo, 'worktree', 'list', '--porcelain').split('\n\n')
               if '\nbranch ' + ref + '\n' in '\n' + block + '\n']
    parents = [path for path in parents if git(path, 'rev-parse', '--is-inside-work-tree') == 'true']
    old = git(repo, 'for-each-ref', '--format=%(objectname)', ref)
    if previous and old not in (previous, integrated):
        raise ValueError('The local parent advanced after delivery; ask outer before replacing it.')
    if parents:
        clean(parents[0])
        command = ('reset', '--keep') if previous else ('merge', '--ff-only')
        git(parents[0], *command, integrated)
    else:
        if old and not previous:
            git(repo, 'merge-base', '--is-ancestor', old, integrated)
        git(repo, 'update-ref', ref, integrated, old)


def done_view(context):
    return {'instruction': f'Feature commit already pushed to {context["binding"]["parent_branch"]}. Use amend to revise that pushed feature.'}


def amend(args, context):
    authorize_amendment(args, context)
    repo = Path.cwd()
    check_repo(repo, context['binding'])
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    checkout(context, common, context['state']['integrated'])
    cli('issue', 'status', context['issue_id'], 'in_progress')


def push(args, context):
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    test(repo, binding['test_command'])
    commit = git(repo, 'rev-parse', 'HEAD')
    if git(repo, 'show', '-s', '--format=%P', commit) != git(repo, 'show', '-s', '--format=%P', state['integrated']):
        raise ValueError('Amend the delivered commit in place; do not add commits or start another review loop.')
    advance_parent(repo, binding, commit, state['integrated'])
    state.update(feature=feature_link(repo, binding, commit), diff=diff_report(repo, binding))
    return finish(context, commit)


def finish(context, integrated=None):
    """Reuse publication/cleanup for retained done; only cancellation finishes the SOP."""
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    if repo.resolve() != (common / 'featsship' / context['issue_id']).resolve():
        raise ValueError('Finish from this issue’s prepared feature worktree.')
    cancelled = state.get('cancel_reason')
    amending = context['phase'] == 'amending'
    integrated = integrated or state.get('integrated')
    note = final_note(context)
    os.chdir(common)
    run('git', '--git-dir', str(common), 'worktree', 'remove', str(repo))
    run('git', '--git-dir', str(common), 'branch', '-D', binding['branch'])
    if not cancelled:
        try:
            ref = 'refs/heads/' + binding['parent_branch']
            lease = ['--force-with-lease=' + ref + ':' + state['integrated']] if amending else []
            run('git', '--git-dir', str(common), 'push', *lease, 'origin', integrated + ':' + ref)
        except ValueError as error:
            checkout(context, common, integrated)
            if amending:
                return {'phase': 'amending', 'instruction': 'Parent push failed; restored the amendment checkout. Resolve with outer and retry push without review. ' + str(error)}
            state['integration_error'] = 'Parent push failed; restored the local branch/worktree for Reviewer recovery. ' + str(error)
            return {'phase': 'integration_error'}
        state['integrated'] = integrated
    parent = context['binding']['main_issue_id']
    receipt = comment(parent, note, binding['dispatch_thread'])
    if not cancelled:
        cli('issue', 'comment', 'resolve', receipt['id'])
    cli('issue', 'metadata', 'delete', context['issue_id'], '--key', 'git_base_commit')
    cli('issue', 'status', context['issue_id'], 'cancelled' if cancelled else 'done')
    return {'phase': Workflow.FINISHED if cancelled else 'done',
            'this_round_reply_guidance': FINAL_DONE}


workflow = Workflow(
    State('develop', 'Developer: implement the issue request on MAIN’s feature branch in the current issue folder. '
          'Keep one feature commit; amend corrections, never merge. Continue any retained rebase, then test and submit.',
          initial=True, precheck=observed, view=enter_develop, owner=owner('developer'), preview='Developer: implement, test and submit the feature.'),
    State('review', REVIEW_PROMPT,
          precheck=observed, owner=owner('reviewer'), view=review_view, preview='Reviewer: inspect the submitted revision and selected review questions.'),
    State('manual_approve', 'Approve integration?',
          precheck=observed, owner=outer_owner),
    State('integration_error', INTEGRATION_PROMPT, precheck=observed, view=integration_view, owner=owner('reviewer'), preview='Reviewer: diagnose integration failure and select recovery or rework.'),
    State('done', 'Feature commit already pushed to the parent branch. Use amend to revise that pushed feature.',
          precheck=observed, view=done_view, owner=owner('developer'), preview='Feature pushed. Amend only on an explicit outer request.'),
    State('amending', 'Developer: amend the delivered commit in place, verify and interact briefly with outer as needed. No review loop; use push when ready.',
          precheck=observed, owner=owner('developer')),
    Option('submit', prompt='Test and request independent review; push only if manual.', action=submit,
           params=(Parameter('--summary', 'Delivered behavior and evidence'),)),
    Option('approve', prompt='Approve the revision; manual config waits for outer approval.', action=verdict,
           params=(Parameter('--finding', 'Review answers and evidence'),)),
    Option('rework', prompt='rework', action=verdict,
           params=(Parameter('--finding', 'Quick diagnosis and required Developer corrections'),)),
    Option('cancel', prompt='cancel', action=verdict,
           params=(Parameter('--reason', 'Concrete cancellation blocker'),)),
    Option('final_approve', prompt='approve', action=merge_approved),
    Option('environment_repaired', prompt='Reviewer recovery completed: retry approved integration with required checks.'),
    Option('amend', prompt='ONLY explicit outer request: recreate the issue checkout at the delivered commit and reopen the issue.', action=amend),
    Option('push', prompt='Publish the amended commit, clean up and mark the native issue done.', action=push),
    Branch('approval', 'manual config?',
           select=lambda args, context: 'manual_approve' if context['binding']['manual'] else 'final_approve'),
    Branch('merge_result', 'Integration successful?'),
    edges=(
        ('develop', 'submit'), ('develop', 'cancel'),
        ('submit', 'review'),
        ('review', 'approve'), ('review', 'rework'), ('review', 'cancel'),
        ('approve', 'approval'),
        ('approval', 'manual_approve'), ('approval', 'final_approve'),
        ('manual_approve', 'rework'), ('manual_approve', 'final_approve'), ('manual_approve', 'cancel'),
        ('final_approve', 'merge_result'),
        ('merge_result', 'integration_error'), ('merge_result', 'done'),
        ('integration_error', 'environment_repaired'), ('integration_error', 'rework'),
        ('environment_repaired', 'final_approve'),
        ('rework', 'develop'), ('cancel', Workflow.FINISHED),
        ('done', 'amend'), ('amend', 'amending'),
        ('amending', 'push'), ('push', 'done'),
    ),
    params=(Parameter('--thread', 'Native triggering comment UUID', required=False),),
)
