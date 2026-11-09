"""Local GitHub fixture; writes require the approved commit on remote main."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    path = Path(os.environ['FEATSSSHIP_FAKE_DB'])
    db = json.loads(path.read_text())
    args = sys.argv[1:]
    db['github_calls'].append(args)
    assert args[:1] == ['issue'] and args[2] == db['github']['url'], args
    issue = db['github']
    result = ''
    if args[1] == 'view':
        fields = args[args.index('--json') + 1].split(',')
        result = json.dumps({key: issue[key] for key in fields})
    else:
        subprocess.run(['git', '--git-dir', issue['remote'], 'merge-base', '--is-ancestor',
                        issue['approved_commit'], 'main'], check=True, capture_output=True)
        if args[1] == 'comment':
            body = Path(args[args.index('--body-file') + 1]).read_text()
            issue['comments'].append({'body': body})
        elif args[1] == 'close':
            if db.pop('github_fail_close', False):
                path.write_text(json.dumps(db))
                raise ValueError('Simulated GitHub close failure after comment')
            assert issue['comments'], 'A resolution comment must precede closure'
            issue['state'] = 'CLOSED'
        else:
            raise ValueError('Unsupported GitHub call: ' + str(args))
    path.write_text(json.dumps(db))
    print(result)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
