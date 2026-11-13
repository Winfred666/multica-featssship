"""Develop and review in the issue's shared folder and branch; report to MAIN."""
from pathlib import Path
import os
import json
import re
import subprocess
from html import escape
from urllib.parse import quote

from common import DISPATCH_KEY, ROUND_DONE, REWORK_DONE, check_repo, clean, cli, comment, feature_config, git, run, test
from sop import Branch, Completed, Option, Parameter, State, Workflow

CACHE_VIEW = False
FINAL_DONE = 'directly and silently end this turn'

REVIEW_PROMPT = ('Reviewer: inspect the submitted diff in this issue\'s shared folder and branch '
                 'without source edits or tests. '
                 'Answer the selected review questions in --finding. Approve or return corrections.')

INTEGRATION_PROMPT = ('Reviewer: quickly diagnose this integration failure, not a broad investigation. '
                      'Choose environment repair or repo-originated defect/conflict rework. '
                      'Within existing authorization, repair only out-of-repo/local environment or installed execution/path setup, '
                      'never tracked product code or assertions. Never bypass failing required checks. '
                      'Retry preserves existing approval only for the unchanged approved revision; '
                      'changed revisions need submission, review and any required outer approval. '
                      'For REBASE CONFLICT, renew/complete the unfinished table and include it in --finding on rework. '
                      'Environment retry needs no completed table. '
                      'Preserve interrupted Git/rebase state; do not abort or restart it blindly.')

# TODO: break agent-as-middle-layer: the runtime should stop until superior input directly.
MANUAL_WAIT = 'Auto review passed; wait for superior instruction. Directly and silently end this turn.'


def owner(role):
    return lambda context: cli('agent', 'get', context['binding'][role + '_id'])


def handoff(args, context, owner):
    comment(context['issue_id'], f'[@{owner["name"]}](mention://agent/{owner["id"]}) ' +
            (args.summary + '\n\n' + context['state']['diff'] if args.event == 'submit' else args.finding if args.event == 'rework' else context['result']['next_step']['instruction']),
            args.thread, steer_agent=owner['id'])
    context['handoff'] = REWORK_DONE if context['phase'] == 'develop' else ROUND_DONE


def review_view(context):
    return {'instruction': REVIEW_PROMPT +
            '\n\nReview questions:\n' + '\n'.join('- ' + q for q in context['binding']['questions'])}


def integration_view(context):
    return {'instruction': INTEGRATION_PROMPT + '\n\n' + context['state']['integration_error']}


def retry_integration(args, context):
    repo, binding, state = Path.cwd(), context['binding'], context['state']
    check_repo(repo, binding)
    if git(repo, 'rev-parse', 'refs/heads/' + binding['branch']) != state['commit']:
        return {'accepted': False, 'instruction': 'The approved revision changed. Choose rework for fresh submission, review and approval.'}
    state.pop('integration_error', None)


def observed(context):
    issue = cli('issue', 'get', context['issue_id'])
    context.update(issue=issue, binding=feature_config(issue))
    if issue['status'] == 'cancelled' or (issue['status'] == 'done' and context['phase'] not in ('done', 'amending')):
        context['handoff'] = FINAL_DONE
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
    context['state'].update(commit=feature, summary=args.summary,
                            feature=feature_link(repo, binding, feature), diff=diff_report(repo, binding))
    cli('issue', 'status', context['issue_id'], 'in_review')


def diff_report(repo, binding):
    rows = [line.split('\t', 2) for line in git(repo, 'diff', '--numstat',
            'origin/' + binding['parent_branch'] + '...HEAD').splitlines()]
    sizes = [(int(added) if added != '-' else 0, int(deleted) if deleted != '-' else 0, path)
             for added, deleted, path in rows]
    totals = f'+{sum(a for a, _, _ in sizes)} / -{sum(d for _, d, _ in sizes)} lines across {len(rows)} files'
    table = ['| File | Added / deleted |', '| --- | --- |']
    table += [f'| `{path}` | +{added} / -{deleted} |'
              for added, deleted, path in sorted(sizes, key=lambda row: row[0] + row[1], reverse=True)[:3]]
    return totals + ('\n\n' + '\n'.join(table) if rows else '')


def final_note(context):
    state, binding = context['state'], context['binding']
    if state.get('cancel_reason'):
        return '/note sub-issue CANCELLED: ' + state['cancel_reason']
    note = '/note sub-issue DONE: ' + state['feature'] + '.'
    mirror = re.fullmatch(r'\[.+\]\((https://github\.com/[^)]+/issues/[0-9]+)\)', context['issue']['title'])
    source = binding.get('github_issue') or (mirror[1] if mirror else None)
    if source:
        issue = json.loads(run('gh', 'issue', 'view', source, '--json', 'state,title,url'))
        if issue['state'] == 'CLOSED':
            note += f" GitHub issue [{issue['title']}]({issue['url']}) solved and closed."
    return note + '\n\n' + state['diff']


def outer_confirmed(args, context):
    if context['phase'] == 'done' and not args.thread:
        raise ValueError('Amend only on an explicit outer request; pass its comment UUID with --thread.')
    rows = cli('issue', 'comment', 'list', context['issue_id'], '--thread', args.thread or context['state']['manual_comment_id'], '--tail', '30')
    gate = next(row for row in rows if row['id'] == context['state']['manual_comment_id']) if context['phase'] == 'manual_approve' else None
    outer = next((row for row in reversed(rows) if row['id'] == args.thread or
                  (not args.thread and (row.get('author_type') == 'member' or row.get('author_id') == context['binding']['delegator_id']))), None)
    if (not outer or (gate and rows.index(outer) <= rows.index(gate))
            or not (outer.get('author_type') == 'member' or outer.get('author_id') == context['binding']['delegator_id'])):
        raise ValueError('ONLY outer allowed: pass the superior instruction with --thread; manual approval must follow automated review.')


def verdict(args, context):
    """```dot
    digraph verdict { node [shape=box]; inspect [label="Read submitted revision"];
        rework [label="Return corrections to Developer"];
        approve [label="Approve; Reviewer owns integration"];
        inspect -> rework [label="rework"]; inspect -> approve [label="approve"]; }
    ```"""
    if context['phase'] == 'manual_approve' and args.event != 'rework':
        outer_confirmed(args, context)
    if args.event == 'cancel':
        context['state']['cancel_reason'] = args.reason
        return finish(context)
    binding, state = context['binding'], context['state']
    if not (context['phase'] in ('manual_approve', 'integration_error') and args.event == 'rework') and git(shared_repo(context), 'rev-parse', 'HEAD') != state['commit']:
        raise ValueError('Review the exact submitted revision; changed code needs a new submission.')
    if args.event == 'approve':
        state['finding'] = args.finding
        if context['phase'] == 'review' and binding['manual']:
            row = comment(context['issue_id'], MANUAL_WAIT + '\n\nONLY outer allowed: reply approve, rework or cancel.', args.thread)
            state['manual_comment_id'] = row['id']
            context['handoff'] = MANUAL_WAIT
            return {'phase': 'manual_approve'}
    if args.event == 'rework':
        if context['phase'] == 'integration_error':
            state.pop('integration_error', None)
        cli('issue', 'status', context['issue_id'], 'in_progress')
    return {'phase': 'approve' if args.event == 'approve' else 'develop'}


def retained_rebase(repo):
    return next((repo / git(repo, 'rev-parse', '--git-path', name)
                 for name in ('rebase-merge', 'rebase-apply')
                 if (repo / git(repo, 'rev-parse', '--git-path', name)).is_dir()), None)


def rebase_conflict_report(repo, binding, incoming, upstream, paths):
    def commit(label, revision):
        description = git(repo, 'log', '-1', '--format=%b', revision)
        if not description:
            description = git(repo, 'show', '--format=', '--shortstat', revision)
        return f'{label}: {feature_link(repo, binding, revision)}' + ('<br>' + escape(' '.join(description.split())[:180]) if description else '')

    def excerpt(lines):
        return escape(' / '.join(lines[:3])[:240]).replace('|', '&#124;').replace('[', '&#91;').replace(']', '&#93;') or '∅'

    def locate(original, blocks):
        located = []
        for block in blocks:
            matches = [i + 1 for i in range(len(original) - len(block) + 1)
                       if block and original[i:i + len(block)] == block]
            located.append((block, matches[0] if len(matches) == 1 else None))
        return located

    def linked_excerpt(revision, path, located, fallback):
        remote = binding['repository'].removesuffix('.git').replace('git@github.com:', 'https://github.com/').rstrip('/')
        url = remote + '/blob/' + revision + '/' + quote(path)
        cells = []
        for block, start in located or [(fallback, None)]:
            anchor = f'#L{start}-L{start + len(block) - 1}' if start else ''
            cells.append(f'[{excerpt(block)}]({url}{anchor})' if block else '∅')
        return '<br>'.join(cells)

    rows = ['| File | Upstream line/range | Conflicting upstream source commit(s) | Upstream (main) excerpt | Incoming (feature) excerpt | Reviewer diagnosis |',
            '| --- | --- | --- | --- | --- | --- |']
    for path in paths[:3]:
        blocks, original = {2: [], 3: []}, {2: [], 3: []}
        side = None
        file = repo / path
        lines = file.read_text(errors='replace').splitlines() if file.is_file() else []
        for line in lines:
            marker = re.match(r'^(<{7,}|\|{7,}|={7,}|>{7,})(?: |$)', line)
            if marker:
                side = {'<': 2, '=': 3}.get(marker[1][0])
                if side:
                    blocks[side].append([])
            elif side:
                blocks[side][-1].append(line)
        for entry in git(repo, 'ls-files', '-u', '--', path).splitlines():
            metadata, _ = entry.split('\t', 1)
            _, blob, stage = metadata.split()
            if int(stage) in original:
                content = subprocess.run(['git', '-C', str(repo), 'cat-file', 'blob', blob],
                                         check=True, capture_output=True).stdout
                original[int(stage)] = ([content[:32].hex()] if b'\0' in content else
                                        content.decode(errors='replace').splitlines())
        located = {stage: locate(original[stage], blocks[stage]) for stage in original}
        ranges, sources = [], []
        for block, start in located[2]:
            if start:
                ranges.append(f'L{start}-L{start + len(block) - 1}')
                blame = git(repo, 'blame', '--line-porcelain', '-L', f'{start},+{len(block)}', upstream, '--', path)
                sources += re.findall(r'^([0-9a-f]{40}) \d+ \d+', blame, re.M)
            else:
                ranges.append('pending')
        provenance = '<br>'.join(feature_link(repo, binding, revision).replace('|', '&#124;')
                                for revision in dict.fromkeys(sources))
        if not ranges or 'pending' in ranges:
            provenance += ('<br>' if provenance else '') + 'pending: Reviewer to locate source'
        rows.append(f'| {escape(path).replace("|", "&#124;")} | {", ".join(ranges) or "pending"} | {provenance} | ' +
                    linked_excerpt(upstream, path, located[2], original[2]) + ' | ' +
                    linked_excerpt(incoming, path, located[3], original[3]) + ' | pending |')
    return ('REBASE CONFLICT\n\n' + commit('Incoming feature commit', incoming) + '\n\n' +
            commit('Upstream main snapshot', upstream) + '\n\nUnfinished table:\n\n' + '\n'.join(rows) +
            '\n\nReviewer: renew/complete this table and include it in --finding when selecting rework. '
            'Environment retry needs no completed table.')


def merge_approved(args, context):
    """```dot
    digraph merge_approved { node [shape=box]; check [label="Reviewer: verify approved HEAD"];
        rebase [label="Rebase feature onto latest main; continue retained rebase"];
        changed [shape=diamond, label="Conflict or changed revision?"];
        rework [label="Developer: resolve if needed; resubmit for review"];
        finish [label="Test, advance main, clean up and push"];
        judge [label="Reviewer: quick-judge integration error"];
        check -> rebase -> changed; changed -> rework [label="yes"];
        rebase -> judge [label="error"];
        changed -> finish [label="no"]; }
    ```"""
    if context['phase'] == 'manual_approve':
        outer_confirmed(args, context)
    repo, binding, state = Path.cwd(), context['binding'], context['state']
    commit = state['commit']
    try:
        check_repo(repo, binding)
        rebase = retained_rebase(repo)
        if rebase:
            if ((rebase / 'orig-head').read_text().strip() != commit or
                    (rebase / 'head-name').read_text().strip() != 'refs/heads/' + binding['branch']):
                raise ValueError('The retained rebase does not belong to the approved revision and MAIN branch. Preserve it for Developer.')
        else:
            shared_repo(context)
            if git(repo, 'rev-parse', 'HEAD') != commit:
                raise ValueError('Integrate the exact approved revision; changed code needs a new review.')
            test(repo, binding['test_command'])
        if binding['manual'] and git(repo, 'ls-remote', 'origin', 'refs/heads/' + binding['branch']).split()[0] != commit:
            raise ValueError('The remote feature branch changed after submission.')
        if rebase:
            git(repo, 'rebase', '--continue')
        else:
            git(repo, 'fetch', 'origin', binding['parent_branch'])
            upstream = git(repo, 'rev-parse', 'origin/' + binding['parent_branch'])
            git(repo, 'rebase', upstream)
        if git(repo, 'rev-parse', 'HEAD') != commit:
            cli('issue', 'status', context['issue_id'], 'in_progress')
            return {'phase': 'develop', 'instruction': 'Rebased onto latest main. Submit the changed revision for fresh review and approval; keep one feature commit.'}
        test(repo, binding['test_command'])
        advance_parent(repo, binding, commit)
        state['integrated'] = commit
    except ValueError as error:
        state['integration_error'] = 'Integration stopped: ' + str(error)
        paths = [path for path in git(repo, 'diff', '--name-only', '--diff-filter=U', '-z').split('\0') if path]
        rebase = retained_rebase(repo)
        if rebase and paths:
            state['integration_error'] = rebase_conflict_report(repo, binding, commit,
                (rebase / 'onto').read_text().strip(), paths)
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
    if context['args'].event == 'init':
        context['handoff'] = FINAL_DONE
    return {}


def amend(args, context):
    outer_confirmed(args, context)
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
            cli('issue', 'status', context['issue_id'], 'in_progress')
            if amending:
                return {'phase': 'amending', 'instruction': 'Parent push failed; restored the amendment checkout. Resolve with outer and retry push without review. ' + str(error)}
            return {'phase': 'develop', 'instruction': 'Parent push failed; restored the local branch/worktree for rework. Rebase onto the latest parent and submit for review again; keep one feature commit. ' + str(error)}
        state['integrated'] = integrated
    parent = context['binding']['main_issue_id']
    main = cli('issue', 'get', parent)
    receipt = comment(parent, note, binding['dispatch_thread'])
    if not cancelled:
        cli('issue', 'comment', 'resolve', receipt['id'])
    cli('issue', 'metadata', 'delete', context['issue_id'], '--key', 'git_base_commit')
    progress = json.loads(main.get('metadata', {}).get(DISPATCH_KEY, '{}'))
    if progress.get('issue_id') == context['issue_id']:
        for key in ('branch_base', 'remote_reserved'):
            progress.pop(key, None)
        cli('issue', 'metadata', 'set', parent, '--key', DISPATCH_KEY,
            '--value', json.dumps(progress), '--type', 'string')
    cli('issue', 'status', context['issue_id'], 'cancelled' if cancelled else 'done')
    context['handoff'] = FINAL_DONE
    return {'phase': Workflow.FINISHED if cancelled else 'done', 'instruction': FINAL_DONE}


workflow = Workflow(
    State('develop', 'Developer: implement the issue request on MAIN’s feature branch in the current issue folder. '
          'Keep one feature commit; amend corrections, never merge. Continue any retained rebase, then test and submit.', initial=True, precheck=observed, view=enter_develop, owner=owner('developer'),
          options=(Option('submit', 'review', 'Test and request independent review; push only if manual.', submit,
                          params=(Parameter('--summary', 'Delivered behavior and evidence'),)),
                   Option('cancel', Workflow.FINISHED, 'Cancel for wrong feature scope, incomplete Git/version infrastructure, or refactoring beyond the allowed edit budget; preserve or commit edits first.', verdict,
                          params=(Parameter('--reason', 'Concrete blocker preventing this feature'),)),)),
    State('review', REVIEW_PROMPT + '\n\nAnswer this issue’s selected questions from the shared delegation document.',
          precheck=observed, owner=owner('reviewer'), view=review_view, options=(
              Option('approve', 'approval', 'Approve the revision; manual config waits for outer approval.', verdict,
                     params=(Parameter('--finding', 'Review answers and evidence'),)),
              Option('rework', 'develop', 'Send corrections to Developer.', verdict,
                     params=(Parameter('--finding', 'Concrete corrections'),)),
              Option('cancel', Workflow.FINISHED, 'Cancel for wrong scope, incomplete Git/version infrastructure or refactoring beyond the edit budget; script cleans locally without merging or pushing.', verdict,
                     params=(Parameter('--reason', 'Concrete cancellation blocker'),)))),
    Branch('approval', 'manual config?', {'manual': 'manual_approve', 'automatic': 'approve'}),
    State('approve', 'Reviewer: automated review passed. Use final_approve to rebase onto latest main; changed revisions return for fresh review and approval.',
          precheck=observed, owner=owner('reviewer'), options=(Option('final_approve', 'merge_result', 'Rebase approved work; changed revisions return for review, unchanged approval ships.', merge_approved),)),
    State('manual_approve', MANUAL_WAIT, precheck=observed, owner=owner('reviewer'), options=(
        Option('rework', 'develop', 'Reviewer: return corrections to Developer without integration.', verdict,
               params=(Parameter('--finding', 'Review corrections or superior-requested rework'),)),
        Option('final_approve', 'merge_result', 'ONLY outer allowed: rebase approved work; changed revisions need fresh review and approval.', merge_approved),
        Option('cancel', Workflow.FINISHED, 'ONLY outer allowed: cancel the feature and clean up without integration.', verdict,
               params=(Parameter('--reason', 'Superior cancellation reason'),)),
    )),
    Branch('merge_result', 'Integration error / changed revision?', {'error': 'integration_error', 'rework': 'develop', 'merged': 'done'}),
    State('integration_error', INTEGRATION_PROMPT, precheck=observed, view=integration_view, owner=owner('reviewer'), options=(
        Option('environment_repaired', 'approve', 'Out-of-repo/environment repair completed: retry automatic approve with existing unchanged-revision approval.', retry_integration),
        Option('rework', 'develop', 'Repo-originated defect/conflict: return to Developer through the existing submission and review gates; preserve interrupted Git state.', verdict,
               params=(Parameter('--finding', 'Quick diagnosis and corrections; for REBASE CONFLICT include the renewed table'),)),
    )),
    State('done', FINAL_DONE + '; retain this SOP state. Amend only on an explicit outer request.',
          precheck=observed, view=done_view, owner=owner('reviewer'), options=(
              Option('amend', 'amending', 'ONLY explicit outer request: recreate the issue checkout at the delivered commit and reopen the issue.', amend),)),
    State('amending', 'Developer: amend the delivered commit in place, verify and interact briefly with outer as needed. No review loop; use push when ready.',
          precheck=observed, owner=owner('developer'), options=(
              Option('push', 'done', 'Publish the amended commit, clean up and mark the native issue done.', push),)),
    params=(Parameter('--thread', 'Native triggering comment UUID', required=False),), handoff=handoff,
)
