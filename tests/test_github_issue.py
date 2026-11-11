from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'delegation'))
from github_issue import issue_link, mirror_title


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
