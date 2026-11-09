"""Report committed line changes and the three files with the largest diffs."""
from common import git


def commit_report(repo, base='origin/main', commit='HEAD'):
    commit = git(repo, 'rev-parse', '--verify', commit + '^{commit}')
    base = git(repo, 'merge-base', base, commit)
    entries = iter(git(repo, 'diff', '--numstat', '-z', '--find-renames', base, commit, '--').split('\0'))
    files = []
    for entry in entries:
        if not entry:
            continue
        added, deleted, path = entry.split('\t', 2)
        if not path:
            next(entries)  # Git emits the old and new rename paths separately with -z.
            path = next(entries)
        files.append({'path': path, 'added': int(added) if added != '-' else None,
                      'deleted': int(deleted) if deleted != '-' else None})
    return {'base': base, 'commit': commit, 'files_changed': len(files),
            'added': sum(row['added'] or 0 for row in files),
            'deleted': sum(row['deleted'] or 0 for row in files),
            'binary_files': sum(row['added'] is None for row in files),
            'largest_files': sorted(files, key=lambda row: (-(row['added'] or 0) - (row['deleted'] or 0), row['path']))[:3]}
