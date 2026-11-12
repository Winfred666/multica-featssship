"""Develop and review in the issue's shared folder and branch; report to MAIN."""
from pathlib import Path
import os
import json
import re

from common import DISPATCH_KEY, ROUND_DONE, REWORK_DONE, check_repo, clean, cli, comment, entry_command, feature_config, git, run, test
from sop import Branch, Completed, Option, Parameter, State, Workflow

CACHE_VIEW = False
FINAL_DONE = 'directly and silently end this turn'

REVIEW_PROMPT = ('Reviewer: inspect the submitted diff in this issue\'s shared folder and branch. '
                 'Review without source edits or tests; after approval, own scripted integration, push and completion. '
                 'Answer the acceptance and review questions in --finding. Approve or return corrections.')

# TODO: break agent-as-middle-layer: the runtime should stop until superior input directly.
MANUAL_WAIT = 'Auto review passed; wait for superior instruction. Directly and silently end this turn.'


def owner(role):
    return lambda context: cli('agent', 'get', context['binding'][role + '_id'])


def handoff(args, context, owner):
    comment(context['issue_id'], f'[@{owner["name"]}](mention://agent/{owner["id"]}) ' +
            (args.summary + '\n\n' + context['state']['diff'] if args.event == 'submit' else args.finding if args.event == 'rework' else context['result']['next_step']['instruction']) + '\n\n' + entry_command('multica-featssship-develop-review'),
            args.thread, steer_agent=owner['id'])
    context['handoff'] = REWORK_DONE if context['phase'] == 'develop' else ROUND_DONE


def review_view(context):
    request = context['issue']['description'].rsplit('\n\n' + entry_command('multica-featssship-develop-review'), 1)[0]
    return {'instruction': REVIEW_PROMPT + '\n\nIssue criteria (read-only reference):\n' + request +
            '\n\nReview questions:\n' + '\n'.join('- ' + q for q in context['binding']['questions'])}


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
    if git(repo, 'rev-list', '--count', '--no-merges', 'origin/' + binding['parent_branch'] + '..HEAD') != '1':
        raise ValueError('Keep one non-merge feature commit; amend corrections. Conflict-resolution merge commits are allowed.')
    test(repo, binding['test_command'])
    ref = 'refs/heads/' + binding['branch']
    if binding['manual']:
        git(repo, 'push', '--force-with-lease=' + ref + ':' + context['state'].get('commit', context['issue']['metadata'].get('git_base_commit', '')), 'origin', 'HEAD:' + ref)
    feature = git(repo, 'log', '--no-merges', '--format=%H', 'origin/' + binding['parent_branch'] + '..HEAD')
    context['state'].update(commit=git(repo, 'rev-parse', 'HEAD'), summary=args.summary,
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
    if not (context['phase'] == 'manual_approve' and args.event == 'rework') and git(shared_repo(context), 'rev-parse', 'HEAD') != state['commit']:
        raise ValueError('Review the exact submitted revision; changed code needs a new submission.')
    if args.event == 'approve':
        state['finding'] = args.finding
        if context['phase'] == 'review' and binding['manual']:
            row = comment(context['issue_id'], MANUAL_WAIT + '\n\nONLY outer allowed: reply approve, rework or cancel.', args.thread)
            state['manual_comment_id'] = row['id']
            context['handoff'] = MANUAL_WAIT
            return {'phase': 'manual_approve'}
    if args.event == 'rework':
        cli('issue', 'status', context['issue_id'], 'in_progress')
    return {'phase': 'approve' if args.event == 'approve' else 'develop'}


def merge_approved(args, context):
    """```dot
    digraph merge_approved { node [shape=box]; check [label="Reviewer: verify approved HEAD"];
        merge [label="Merge parent; test and advance local main"];
        conflict [shape=diamond, label="Merge conflict?"];
        rework [label="Resolve merge; commit and resubmit"];
        finish [label="Publish, clean up and resolve MAIN receipt; retain done"];
        check -> merge -> conflict; conflict -> rework [label="yes"];
        conflict -> finish [label="no"]; }
    ```"""
    if context['phase'] == 'manual_approve':
        outer_confirmed(args, context)
    repo, binding, state = shared_repo(context), context['binding'], context['state']
    commit = state['commit']
    if git(repo, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Merge the exact approved revision; changed code needs a new review.')
    try:
        test(repo, binding['test_command'])
        if binding['manual'] and git(repo, 'ls-remote', 'origin', 'refs/heads/' + binding['branch']).split()[0] != commit:
            raise ValueError('The remote feature branch changed after submission.')
        git(repo, 'fetch', 'origin', binding['parent_branch'])
        git(repo, 'merge', '--no-edit', 'origin/' + binding['parent_branch'])
        test(repo, binding['test_command'])
        integrated = git(repo, 'rev-parse', 'HEAD')
        advance_parent(repo, binding, integrated)
        state['integrated'] = integrated
    except ValueError as error:
        cli('issue', 'status', context['issue_id'], 'in_progress')
        return {'phase': 'develop', 'instruction': 'Integration rework: resolve any merge conflict in this worktree, merge the latest parent, commit the resolution as a merge commit and submit for review again. ' + str(error)}
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
            return {'phase': 'develop', 'instruction': 'Parent push failed; restored the local branch/worktree for rework. Merge the latest parent, commit the resolution and submit again. ' + str(error)}
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
          'Keep one non-merge feature commit; amend corrections. Conflict-resolution merge commits are allowed. Test and submit.', initial=True, precheck=observed, view=enter_develop, owner=owner('developer'),
          options=(Option('submit', 'review', 'Test and request independent review; push only if manual.', submit,
                          params=(Parameter('--summary', 'Delivered behavior and evidence'),)),
                   Option('cancel', Workflow.FINISHED, 'Cancel for wrong feature scope, incomplete Git/version infrastructure, or refactoring beyond the allowed edit budget; preserve or commit edits first.', verdict,
                          params=(Parameter('--reason', 'Concrete blocker preventing this feature'),)),)),
    State('review', REVIEW_PROMPT + '\n\nAnswer this issue’s selected questions from the shared delegation document.',
          precheck=observed, owner=owner('reviewer'), view=review_view, options=(
              Option('approve', 'approval', 'Approve the revision; manual config waits for outer approval.', verdict,
                     params=(Parameter('--finding', 'Acceptance answer and review evidence'),)),
              Option('rework', 'develop', 'Send corrections to Developer.', verdict,
                     params=(Parameter('--finding', 'Concrete corrections'),)),
              Option('cancel', Workflow.FINISHED, 'Cancel for wrong scope, incomplete Git/version infrastructure or refactoring beyond the edit budget; script cleans locally without merging or pushing.', verdict,
                     params=(Parameter('--reason', 'Concrete cancellation blocker'),)))),
    Branch('approval', 'manual config?', {'manual': 'manual_approve', 'automatic': 'approve'}),
    State('approve', 'Reviewer: automated review passed. Use final_approve now to merge into local main, then clean up and push automatically.',
          precheck=observed, owner=owner('reviewer'), options=(Option('final_approve', 'merge_result', 'Merge approved work; conflict returns to development, success retains done.', merge_approved),)),
    State('manual_approve', MANUAL_WAIT, precheck=observed, owner=owner('reviewer'), options=(
        Option('rework', 'develop', 'Reviewer: return corrections to Developer without integration.', verdict,
               params=(Parameter('--finding', 'Review corrections or superior-requested rework'),)),
        Option('final_approve', 'merge_result', 'ONLY outer allowed: merge approved work, then clean up and push automatically.', merge_approved),
        Option('cancel', Workflow.FINISHED, 'ONLY outer allowed: cancel the feature and clean up without integration.', verdict,
               params=(Parameter('--reason', 'Superior cancellation reason'),)),
    )),
    Branch('merge_result', 'Merge conflict / rework?', {'rework': 'develop', 'merged': 'done'}),
    State('done', FINAL_DONE + '; retain this SOP state. Amend only on an explicit outer request.',
          precheck=observed, view=done_view, owner=owner('reviewer'), options=(
              Option('amend', 'amending', 'ONLY explicit outer request: recreate the issue checkout at the delivered commit and reopen the issue.', amend),)),
    State('amending', 'Developer: amend the delivered commit in place, verify and interact briefly with outer as needed. No review loop; use push when ready.',
          precheck=observed, owner=owner('developer'), options=(
              Option('push', 'done', 'Publish the amended commit, clean up and mark the native issue done.', push),)),
    params=(Parameter('--thread', 'Native triggering comment UUID', required=False),), handoff=handoff,
)
