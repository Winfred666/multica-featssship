from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from github_issue import close_issue, issue_link, mirror_title


class SourceIssueTests(unittest.TestCase):
    def test_optional_source_and_mirror(self):
        url = 'https://github.com/owner/repository/issues/42'
        title = '[Save documents](' + url + ')'
        self.assertIsNone(issue_link('Save documents'))
        self.assertEqual(issue_link(title), url)
        self.assertEqual(issue_link('Save documents', url), url)
        self.assertEqual(mirror_title('Save documents', url), title)
        self.assertEqual(mirror_title(title, url), title)
        for invalid in ('https://example.com/owner/repo/issues/42',
                        'https://github.com/owner/repo/pull/42',
                        'https://github.com/owner/repo/issues/0'):
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                issue_link('Save documents', invalid)
        with self.assertRaises(ValueError):
            issue_link(title, 'https://github.com/owner/repository/issues/43')

    def test_already_closed_source_gets_developer_resolution_and_commit_link(self):
        url = 'https://github.com/owner/requests/issues/42'
        bodies = []

        def github(*args):
            if args[1:3] == ('issue', 'comment'):
                bodies.append(Path(args[-1]).read_text())
                return ''
            self.assertEqual(args[1:3], ('issue', 'view'))
            return '{"state": "CLOSED", "comments": []}'

        with patch('github_issue.run', side_effect=github):
            close_issue(url, {'repository': 'git@github.com:owner/target.git'},
                        {'revision': 'abc123'}, {'summary': 'Saved edits.\nUsed the existing writer.', 'answer': 'Reopened successfully.'})
        self.assertEqual(bodies, ['Commit: https://github.com/owner/target/commit/abc123\n\n'
                                 'Saved edits.\nUsed the existing writer.\n\nReopened successfully.'])
