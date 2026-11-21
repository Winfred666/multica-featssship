"""Develop and review in the issue's shared folder and branch; report to MAIN."""
from pathlib import Path
import os
import json
import re
import sys

from featssship import check_repo, clean, cli, comment, feature_config, git, run, test
from thread import check_callback_thread, wake_callback
from sop import Branch, Completed, Option, Parameter, State, Workflow

FINAL_DONE = 'directly and silently end this turn'

REVIEW_PROMPT = ('Reviewer: inspect the submitted diff in this issue\'s shared folder and branch '
                 'without source edits or tests. '
                 'Answer the selected review questions in --finding. Approve or return corrections.')

INTEGRATION_PROMPT = ('Reviewer: quickly judge and recover this integration/publication failure. '
                      'Preserve interrupted Git/rebase state; do not abort or restart it blindly. '
                      'Repair within existing authorization without editing tracked product code or bypassing required checks. '
                      'Hash changes from a clean rebase alone do not require source rework. '
                      'Human working edits on main are stashed/restored during integration; restore conflicts stay on main, not Developer rework. '
                      'Resolve a conflict when the intended newer feature is clear; commit time alone is not semantic evidence. '
                      'Otherwise report the ambiguity to MAIN with report_conflict. '
                      'Choose rework only when Developer corrections are needed; retain submission, review and any required outer approval.')


def owner(role):
    return lambda context: cli('agent', 'get', context['binding'][role + '_id'])


def outer_owner(context):
    binding = context['binding']
    return {'issue_id': binding['main_issue_id'], 'thread': binding['dispatch_thread'],
            'id': None, 'content': ('/note sub-issue DONE' if context['phase'] == 'done' else
                                  'Resolve upstream versus incoming feature intent.' if context['phase'] == 'conflict_decide'
                                  else 'Review passed. Approve integration or return corrections to Developer.')}


def handoff_guidance(context, role, message):
    recipient, state = owner(role)(context), context['state']
    explanation = ('Fill <brief explanation> from the actual feature context. '
                   if role == 'developer' else '')
    return ('Post the following handoff with `multica issue comment add ' + context['issue_id'] +
            ' --content-file <file>` in the current thread; do not put it only in the final response. '
            'Use the facts and links below without retrieving them again. ' + explanation +
            'Then directly and silently end this turn; do not run the receiving role’s callback.\n\n'
            f'[@{recipient["name"]}](mention://agent/{recipient["id"]}) {message}\n\n' +
            ('Impact: <brief explanation>\n\n' if role == 'developer' else '') +
            f'Submitted revision: {state["feature"]}\n\n{state["diff"]}')


def review_view(context):
    return {'instruction': REVIEW_PROMPT +
            '\n\nReview questions:\n' + '\n'.join('- ' + q for q in context['binding']['questions'])}


def integration_view(context):
    stage = ('Main publication and feature checks must succeed before review. Retry preparation, not approval.\n\n'
             if context['state'].get('submission') else '')
    return {'instruction': stage + INTEGRATION_PROMPT + '\n\n' + context['state']['integration_error'] +
            '\n\n' + context['state'].get('conflict_decision', '')}


def report_conflict(args, context):
    context['state']['conflict_comparison'] = args.comparison
    return {'this_round_reply_guidance': 'Explain upstream versus incoming with one minimal visual in the MAIN dispatch thread. '
            'Use the actual feature descriptions and conflicting files; do not infer newer intent from timestamps. '
            'The native questionnaire forwards the decision to MAIN. End this turn without choosing for outer.'}


def conflict_view(context):
    return {'instruction': 'Which feature should survive? Upstream = main; incoming = this feature. '
            'Custom supplies resolution instructions to Reviewer.\n\n' + context['state']['conflict_comparison']}


def choose_conflict(args, context):
    decision = {'use_upstream': 'Keep upstream main in the reported conflict.',
                'use_incoming': 'Keep the incoming feature in the reported conflict.',
                'custom_resolution': getattr(args, 'steer', '')}[args.event]
    context['state']['conflict_decision'] = 'Outer conflict decision: ' + decision
    wake_callback(context, context['binding']['reviewer_id'],
               decision + ' Resolve only the reported conflict, preserve Git state and run required checks. '
               'Do not treat this content decision as approval of unrelated edits or alter approval checkpoints. '
               'If the resolved revision needs fresh review, use the existing rework/submission path.')
    return {'this_round_reply_guidance': FINAL_DONE}


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


def parent_worktrees(repo, binding):
    ref = 'refs/heads/' + binding['parent_branch']
    paths = [block.splitlines()[0][9:] for block in git(repo, 'worktree', 'list', '--porcelain').split('\n\n')
             if '\nbranch ' + ref + '\n' in '\n' + block + '\n']
    return [Path(path) for path in paths if git(path, 'rev-parse', '--is-inside-work-tree') == 'true']


def publish_main(repo, binding, subject):
    """Commit product paths only; leave excluded edits and index entries intact."""
    branch = binding['parent_branch']
    parents = parent_worktrees(repo, binding)
    git(repo, 'fetch', 'origin', branch)
    remote = 'origin/' + branch
    if parents:
        parent = parents[0]
        # Git ignores plus these private/local paths also protect already-staged files.
        exclusions = ('.env*', '*credentials*', '*secret*', '*.pem', '*.key',
                      '.agents/**', '.multica/**', '.state/**', '.venv/**',
                      '__pycache__/**', '*.pyc', 'build/**', 'dist/**', 'generated/**',
                      'logs/**', 'workdirs/**', 'config.local.*')
        paths = ('.', *(':(glob,exclude)**/' + pattern for pattern in exclusions))
        pending = set(git(parent, 'diff', '--name-only', '-z', 'HEAD', '--', *paths).split('\0'))
        pending.update(git(parent, 'ls-files', '--others', '--exclude-standard', '-z', '--', *paths).split('\0'))
        pending.difference_update(git(parent, 'ls-files', '--cached', '--ignored', '--exclude-standard', '-z').split('\0'))
        pending.discard('')
        if pending:
            if not subject or not re.fullmatch(r'[a-z]+(?:\([^()\n]+\))?!?: [^\n]+', subject):
                raise ValueError('Inspect pending main product changes and supply --main-subject with a meaningful semantic subject, usually simplify(<scope>): <change>.')
            literals = [':(literal)' + path for path in sorted(pending)]
            git(parent, 'add', '--all', '--', *literals)
            git(parent, 'commit', '--only', '-m', subject, '--', *literals)
        git(parent, 'merge', '--ff-only', remote)
    else:
        local = git(repo, 'rev-parse', branch)
        base = git(repo, 'merge-base', local, remote)
        if base == local:
            git(repo, 'update-ref', 'refs/heads/' + branch, git(repo, 'rev-parse', remote), local)
        else:
            git(repo, 'merge-base', '--is-ancestor', remote, local)
    ref = 'refs/heads/' + branch
    git(repo, 'push', 'origin', ref + ':' + ref)


def submit(args, context):
    """```dot
    digraph submit { node [shape=box]; main [label="Commit main product edits; push all local main commits"];
        prepare [label="Rebase feature; verify one commit; run required checks"];
        review [label="Push feature only if manual; request Reviewer"];
        recover [label="Reviewer: recover Git failure; source conflicts to Developer"];
        main -> prepare -> review; main -> recover [label="error"]; prepare -> recover [label="error"]; }
    ```"""
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    feature = git(repo, 'rev-parse', 'HEAD')
    state['changes'] = json.loads(args.changes)
    state.setdefault('submitted', state.get('commit', context['issue']['metadata'].get('git_base_commit', '')))
    state.pop('integrated', None)
    state.update(commit=feature, feature=feature_link(repo, binding, feature), diff=diff_report(repo, binding, changes=state['changes']),
                 submission={'main_subject': args.main_subject})
    result = prepare_review(args, context)
    message = (args.summary + '\n\nVerified: `' + binding['test_command'] + '` passed.'
               if result['phase'] == 'review' else state['integration_error'])
    result['this_round_reply_guidance'] = handoff_guidance(context, 'reviewer', message)
    return result


def prepare_review(args, context):
    repo, binding, state = Path.cwd(), context['binding'], context['state']
    submission = state['submission']
    if getattr(args, 'main_subject', None):
        submission['main_subject'] = args.main_subject
    try:
        check_repo(repo, binding)
        rebase = retained_rebase(repo)
        if rebase:
            if ((rebase / 'orig-head').read_text().strip() != state['commit'] or
                    (rebase / 'head-name').read_text().strip() != 'refs/heads/' + binding['branch']):
                raise ValueError('Preserve the unrelated retained rebase for Reviewer judgment.')
            git(repo, 'rebase', '--continue')
        shared_repo(context)
        publish_main(repo, binding, submission['main_subject'])
        # Retain the original revision until a failed rebase has been continued.
        state['commit'] = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'rebase', 'origin/' + binding['parent_branch'])
        feature = git(repo, 'rev-parse', 'HEAD')
        state.update(commit=feature, feature=feature_link(repo, binding, feature), diff=diff_report(repo, binding, changes=state['changes']))
        revisions = 'origin/' + binding['parent_branch'] + '..HEAD'
        if git(repo, 'rev-list', '--count', revisions) != '1' or git(repo, 'rev-list', '--merges', revisions):
            raise ValueError('Keep one feature commit; amend corrections. Do not create merge commits.')
        test(repo, binding['test_command'])
        ref = 'refs/heads/' + binding['branch']
        if binding['manual']:
            lease = state.get('submitted', context['issue']['metadata'].get('git_base_commit', ''))
            git(repo, 'push', '--force-with-lease=' + ref + ':' + lease, 'origin', 'HEAD:' + ref)
        state['submitted'] = feature
        state.pop('integration_error', None)
        cli('issue', 'status', context['issue_id'], 'in_review')
        state.pop('submission')
        return {'phase': 'review'}
    except ValueError as error:
        state['integration_error'] = 'Before review, publication/preparation stopped: ' + str(error)
        return {'phase': 'integration_error'}


def recover(args, context):
    if context['state'].get('submission'):
        return prepare_review(args, context)
    if context['state'].get('amend_draft'):
        return push(args, context)
    return merge_approved(args, context)


def diff_report(repo, binding, base=None, changes=None):
    base = base or git(repo, 'merge-base', 'origin/' + binding['parent_branch'], 'HEAD')
    rows = [line.split('\t', 2) for line in git(repo, 'diff', '--numstat', base, 'HEAD').splitlines()]
    sizes = [(int(added) if added != '-' else 0, int(deleted) if deleted != '-' else 0, path)
             for added, deleted, path in rows]
    totals = f'+{sum(a for a, _, _ in sizes)} / -{sum(d for _, d, _ in sizes)} lines across {len(rows)} files'
    remote = binding['repository'].removesuffix('.git').replace('git@github.com:', 'https://github.com/').rstrip('/')
    head = git(repo, 'rev-parse', 'HEAD')
    totals += f' · [Full diff]({remote}/compare/{base}...{head})'
    largest = sorted(sizes, key=lambda row: row[0] + row[1], reverse=True)[:3]
    if not isinstance(changes, dict) or any(not isinstance(changes.get(path), str) or not changes[path].strip() for _, _, path in largest):
        raise ValueError('Supply --changes as a JSON object mapping each of the three largest changed paths to its behavior explanation.')
    table = ['| File | Added / deleted | Change |', '| --- | --- | --- |']
    table += [f"| `{path}` | +{added} / -{deleted} | {changes[path].replace('|', chr(92) + '|').replace(chr(10), ' ')} |"
              for added, deleted, path in largest]
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
    return note + '\n\nVerified: `' + binding['test_command'] + '` passed.\n\n' + state['diff'] + ('\n\n' + state['main_restore_warning'] if state.get('main_restore_warning') else '')


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
                'The human approval questionnaire goes to MAIN’s dispatch thread; end this turn.'}
    if args.event == 'rework':
        if context['phase'] == 'manual_approve':
            check_callback_thread(context)
        if context['phase'] == 'integration_error':
            state.pop('integration_error', None)
            state.pop('submission', None)
        cli('issue', 'status', context['issue_id'], 'in_progress')
        if context['phase'] == 'manual_approve':
            wake_callback(context, binding['developer_id'], 'Corrections requested: ' + args.finding)
            return {'this_round_reply_guidance': FINAL_DONE}
        return {'this_round_reply_guidance': handoff_guidance(context, 'developer', args.finding)}
    return {}


def retained_rebase(repo):
    return next((repo / git(repo, 'rev-parse', '--git-path', name)
                 for name in ('rebase-merge', 'rebase-apply')
                 if (repo / git(repo, 'rev-parse', '--git-path', name)).is_dir()), None)


def approved_rebase_tree(repo, binding, approved, upstream):
    """Reconstruct a clean replay without touching the index or retained rebase."""
    try:
        if len(git(repo, 'rev-list', '--parents', '-n', '1', approved).split()) != 2:
            raise ValueError('The approved feature must be one non-merge commit.')
        git(repo, 'merge-base', '--is-ancestor', approved + '^', upstream)
        git(repo, 'merge-base', '--is-ancestor', upstream, 'origin/' + binding['parent_branch'])
        return git(repo, 'merge-tree', '--write-tree', '--merge-base=' + approved + '^',
                   upstream, approved).splitlines()[0]
    except ValueError as error:
        raise ValueError('Cannot verify a clean replay of the approved feature onto main. '
                         'Preserve Git state; only corrections to the feature need Developer resubmission and fresh approval.') from error


def verify_approved_revision(repo, binding, approved, revision='HEAD'):
    candidate = git(repo, 'rev-parse', revision)
    if candidate == approved:
        return
    parents = git(repo, 'rev-list', '--parents', '-n', '1', candidate).split()
    if (len(parents) != 2 or
            git(repo, 'rev-parse', candidate + '^{tree}') != approved_rebase_tree(repo, binding, approved, parents[1])):
        raise ValueError(f'Revision {candidate} is not a clean replay of the approved feature; changed code needs Developer resubmission and fresh approval.')


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
            approved_rebase_tree(repo, binding, state['commit'], (rebase / 'onto').read_text().strip())
        else:
            shared_repo(context)
            verify_approved_revision(repo, binding, state['commit'])
            test(repo, binding['test_command'])
        if binding['manual'] and git(repo, 'ls-remote', 'origin', 'refs/heads/' + binding['branch']).split()[0] != state['commit']:
            raise ValueError('The remote feature branch changed after submission.')
        if rebase:
            git(repo, 'rebase', '--continue')
        else:
            git(repo, 'fetch', 'origin', binding['parent_branch'])
            upstream = git(repo, 'rev-parse', 'origin/' + binding['parent_branch'])
            git(repo, 'rebase', upstream)
        shared_repo(context)
        verify_approved_revision(repo, binding, state['commit'])
        commit = git(repo, 'rev-parse', 'HEAD')
        state.update(integrated=commit, feature=feature_link(repo, binding, commit), diff=diff_report(repo, binding, changes=state['changes']))
        test(repo, binding['test_command'])
        warning = advance_parent(repo, binding, commit, approved=state['commit'])
        if warning:
            state['main_restore_warning'] = warning
        state.pop('integration_error', None)
        result = finish(context)
    except ValueError as error:
        state['integration_error'] = 'Integration stopped: ' + str(error)
        result = {'phase': 'integration_error'}
    return result


def advance_parent(repo, binding, integrated, previous=None, approved=None):
    ref = 'refs/heads/' + binding['parent_branch']
    parents = parent_worktrees(repo, binding)
    old = git(repo, 'for-each-ref', '--format=%(objectname)', ref)
    if previous and old not in (previous, integrated):
        raise ValueError('The local parent changed during publication; preserve it and retry against its latest tip.')
    if old == integrated:
        return ''
    warning = ''
    if parents:
        parent = parents[0]
        if retained_rebase(parent) or any((parent / git(parent, 'rev-parse', '--git-path', name)).exists()
                                         for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD')):
            raise ValueError('Main has an interrupted Git operation; preserve it for Reviewer recovery.')
        if approved and git(parent, 'ls-files', '--unmerged'):
            try:
                verify_approved_revision(repo, binding, approved, old)
            except ValueError as error:
                raise ValueError('Cannot verify local main as the approved feature; preserve main and its conflicts for Reviewer recovery.') from error
            # Publication pushes the verified commit, not the checked-out main ref.
            warning = (f'Main conflict and existing stashes left untouched in {parent}; '
                       f'local main remains at {old}. Publishing verified {integrated} directly.')
            print(warning, file=sys.stderr)
            return warning
        stash = None
        if git(parent, 'status', '--porcelain'):
            git(parent, 'stash', 'push', '--include-untracked', '-m', 'featssship: preserve main working edits')
            stash = git(parent, 'rev-parse', 'refs/stash')
        command = ('reset', '--keep') if previous else ('merge', '--ff-only')
        try:
            git(parent, *command, integrated)
        finally:
            if stash:
                try:
                    git(parent, 'stash', 'apply', '--index', stash)
                except ValueError as error:
                    warning = f'Main edits could not be restored automatically in {parent}; stash {stash} retained. {error}'
                    print(warning, file=sys.stderr)
                else:
                    if git(parent, 'rev-parse', 'refs/stash') == stash:
                        git(parent, 'stash', 'drop', 'stash@{0}')
    else:
        if old and not previous:
            git(repo, 'merge-base', '--is-ancestor', old, integrated)
        git(repo, 'update-ref', ref, integrated, old)
    return warning


def done_view(context):
    return {'instruction': final_note(context) + '\n\nRequest rework only to revise this delivered feature.'}


def amend(args, context):
    check_callback_thread(context)
    repo = Path.cwd()
    check_repo(repo, context['binding'])
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    checkout(context, common, context['state']['integrated'])
    cli('issue', 'status', context['issue_id'], 'in_progress')
    wake_callback(context, context['binding']['developer_id'], 'Amend the delivered feature: ' + args.finding)
    return {'this_round_reply_guidance': FINAL_DONE}


def push(args, context):
    repo, binding, state = Path.cwd(), context['binding'], context['state']
    if context['phase'] == 'amending':
        state['changes'] = json.loads(args.changes)
    try:
        check_repo(repo, binding)
        if retained_rebase(repo):
            git(repo, 'rebase', '--continue')
        shared_repo(context)
        commit = git(repo, 'rev-parse', 'HEAD')
        if not state.get('amend_draft'):
            diff_report(repo, binding, state['integrated'], state['changes'])
            state.update(amend_draft=commit, feature=feature_link(repo, binding, commit))
            base = state['integrated']
            # The amended feature is a sibling of the delivered commit. Create a
            # temporary delta commit so Git can replay only the correction.
            commit = git(repo, 'commit-tree', commit + '^{tree}', '-p', base,
                         '-m', git(repo, 'log', '-1', '--format=%s', commit))
            git(repo, 'reset', '--keep', commit)
            state['amend_base'] = base
        ref = 'refs/heads/' + binding['parent_branch']
        while True:
            base = state['amend_base']
            git(repo, 'fetch', 'origin', binding['parent_branch'])
            remote = git(repo, 'rev-parse', 'origin/' + binding['parent_branch'])
            parent = git(repo, 'rev-parse', binding['parent_branch'])
            try:
                git(repo, 'merge-base', '--is-ancestor', parent, remote)
                upstream = remote
            except ValueError:
                try:
                    git(repo, 'merge-base', '--is-ancestor', remote, parent)
                    upstream = parent
                except ValueError:
                    if parent != state['integrated']:
                        raise ValueError('Local main and remote main diverged; preserve both for recovery.')
                    upstream = remote
            if base != upstream:
                state['amend_base'] = upstream
                git(repo, 'rebase', '--onto', upstream, base)
            commit = git(repo, 'rev-parse', 'HEAD')
            test(repo, binding['test_command'])
            amendment_diff = diff_report(repo, binding, upstream, state['changes'])
            try:
                git(repo, 'push', '--force-with-lease=' + ref + ':' + remote, 'origin', commit + ':' + ref)
                break
            except ValueError:
                git(repo, 'fetch', 'origin', binding['parent_branch'])
                if git(repo, 'rev-parse', 'origin/' + binding['parent_branch']) == remote:
                    raise
        state.update(feature=feature_link(repo, binding, commit), diff=amendment_diff)
        state.pop('integration_error', None)
        warning = advance_parent(repo, binding, commit, parent)
        if warning:
            state['main_restore_warning'] = warning
        return finish(context, commit, published=True)
    except ValueError as error:
        if not state.get('amend_draft'):
            raise
        state['integration_error'] = 'Amendment publication stopped; preserve the draft and retained rebase: ' + str(error)
        result = {'phase': 'integration_error'}
        if context['phase'] == 'amending':
            result['this_round_reply_guidance'] = handoff_guidance(context, 'reviewer', state['integration_error'])
        return result


def finish(context, integrated=None, previous=None, parent=None, published=False):
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
            lease = ['--force-with-lease=' + ref + ':' + previous] if amending else []
            if not published:
                run('git', '--git-dir', str(common), 'push', *lease, 'origin', integrated + ':' + ref)
        except ValueError as error:
            checkout(context, common, integrated)
            if amending:
                advance_parent(Path.cwd(), binding, parent, integrated)
                git(Path.cwd(), 'reset', '--keep', state.pop('amend_draft'))
                state.pop('amend_base', None)
                raise
            state['integration_error'] = 'Parent push failed; restored the local branch/worktree for Reviewer recovery. ' + str(error)
            return {'phase': 'integration_error'}
        state['integrated'] = integrated
        state.pop('amend_draft', None)
        state.pop('amend_base', None)
    parent = context['binding']['main_issue_id']
    if cancelled:
        comment(parent, note, binding['dispatch_thread'])
    cli('issue', 'metadata', 'delete', context['issue_id'], '--key', 'git_base_commit')
    cli('issue', 'status', context['issue_id'], 'cancelled' if cancelled else 'done')
    return {'phase': Workflow.FINISHED if cancelled else 'done',
            'this_round_reply_guidance': FINAL_DONE}


workflow = Workflow(
    State('develop', 'Developer: implement the issue request on MAIN’s feature branch in the current issue folder. '
          'Keep one feature commit; amend corrections, never merge. Continue any retained rebase, then submit. '
          'Inspect main product edits and supply --main-subject, usually simplify(<scope>): <change>; '
          'submission publishes main, rebases the feature and runs required checks before review.',
          initial=True, precheck=observed, view=enter_develop, owner=owner('developer'), preview='Developer: implement, test and submit the feature.'),
    State('review', REVIEW_PROMPT,
          precheck=observed, owner=owner('reviewer'), view=review_view, preview='Reviewer: inspect the submitted revision and selected review questions.'),
    State('manual_approve', 'Approve integration?',
          precheck=observed, owner=outer_owner),
    State('integration_error', INTEGRATION_PROMPT, precheck=observed, view=integration_view, owner=owner('reviewer'), preview='Reviewer: diagnose integration failure and select recovery or rework.'),
    State('conflict_decide', 'Choose upstream, incoming or custom resolution.', precheck=observed,
          owner=outer_owner, view=conflict_view, preview='MAIN: decide unresolved upstream versus incoming feature intent.'),
    State('done', 'Feature commit already pushed to the parent branch. Use amend to revise that pushed feature.',
          precheck=observed, view=done_view, owner=outer_owner, preview='Feature pushed. Request rework only for this feature.'),
    State('amending', 'Developer: minimal inline replacements within the delivered feature only; reject another feature. '
          'Verify, then push for automatic replay/publication preserving newer main commits. No fresh review or approval.',
          precheck=observed, owner=owner('developer')),
    Option('submit', prompt='Test and request independent review; push only if manual.', action=submit,
           params=(Parameter('--summary', 'Delivered behavior and evidence'),
                   Parameter('--changes', 'JSON object: changed file paths to behavior explanations'),
                   Parameter('--main-subject', 'Meaningful semantic subject for pending main product changes', required=False))),
    Option('approve', prompt='Approve the revision; manual config waits for outer approval.', action=verdict,
           params=(Parameter('--finding', 'Review answers and evidence'),)),
    Option('rework', prompt='rework', action=verdict,
           params=(Parameter('--finding', 'Quick diagnosis and required Developer corrections'),)),
    Option('cancel', prompt='cancel', action=verdict,
           params=(Parameter('--reason', 'Concrete cancellation blocker'),)),
    Option('final_approve', prompt='approve', action=merge_approved),
    Option('environment_repaired', prompt='Reviewer recovery completed: retry publication with required checks.', action=recover,
           params=(Parameter('--main-subject', 'Semantic subject for pending main product changes', required=False),)),
    Option('report_conflict', prompt='Cannot determine newer intent: ask MAIN.', action=report_conflict,
           params=(Parameter('--comparison', 'Minimal visual comparing actual upstream/incoming features and conflicted files'),)),
    Option('use_upstream', prompt='Keep upstream', action=choose_conflict),
    Option('use_incoming', prompt='Keep incoming', action=choose_conflict),
    Option('custom_resolution', prompt='Custom resolution', action=choose_conflict,
           params=(Parameter('--steer', 'Resolution instructions for Reviewer'),)),
    Option('amend', prompt='Request rework of the delivered feature.', action=amend,
           params=(Parameter('--finding', 'Required corrections to the delivered feature'),)),
    Option('push', prompt='Publish the amended commit, clean up and mark the native issue done.', action=push,
           params=(Parameter('--changes', 'JSON object: changed file paths to behavior explanations'),)),
    Branch('approval', 'manual config?',
           select=lambda args, context: 'manual_approve' if context['binding']['manual'] else 'final_approve'),
    Branch('merge_result', 'Publication successful?'),
    edges=(
        ('develop', 'submit'), ('develop', 'cancel'),
        ('submit', 'merge_result'),
        ('review', 'approve'), ('review', 'rework'), ('review', 'cancel'),
        ('approve', 'approval'),
        ('approval', 'manual_approve'), ('approval', 'final_approve'),
        ('manual_approve', 'rework'), ('manual_approve', 'final_approve'), ('manual_approve', 'cancel'),
        ('final_approve', 'merge_result'),
        ('merge_result', 'integration_error'), ('merge_result', 'done'), ('merge_result', 'review'),
        ('integration_error', 'environment_repaired'), ('integration_error', 'rework'),
        ('integration_error', 'report_conflict'), ('report_conflict', 'conflict_decide'),
        ('conflict_decide', 'use_upstream'), ('conflict_decide', 'use_incoming'), ('conflict_decide', 'custom_resolution'),
        ('use_upstream', 'integration_error'), ('use_incoming', 'integration_error'), ('custom_resolution', 'integration_error'),
        ('environment_repaired', 'merge_result'),
        ('rework', 'develop'), ('cancel', Workflow.FINISHED),
        ('done', 'amend'), ('amend', 'amending'),
        ('amending', 'push'), ('push', 'merge_result'),
    ),
)
