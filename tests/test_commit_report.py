from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from commit_report import commit_report


class CommitReportTest(unittest.TestCase):
    @patch('commit_report.git', side_effect=[
        'revision', 'base',
        '4\t0\tlarge.py\0' '2\t1\tmedium.py\0' '1\t0\tsmall.py\0'
        '0\t2\tremoved.py\0' '-\t-\timage.png\0'])
    def test_totals_and_top_three(self, git):
        report = commit_report('.')
        self.assertEqual((report['added'], report['deleted'], report['files_changed']), (7, 3, 5))
        self.assertEqual([row['path'] for row in report['largest_files']],
                         ['large.py', 'medium.py', 'removed.py'])
