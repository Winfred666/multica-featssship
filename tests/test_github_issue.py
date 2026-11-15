from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'delegation'))
from github_issue import issue_link


class SourceIssueTests(unittest.TestCase):
    def test_optional_source(self):
        url = 'https://github.com/owner/repository/issues/42'
        self.assertIsNone(issue_link(None))
        self.assertEqual(issue_link(url), url)
        for invalid in ('https://example.com/owner/repo/issues/42',
                        'https://github.com/owner/repo/pull/42',
                        'https://github.com/owner/repo/issues/0'):
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                issue_link(invalid)
