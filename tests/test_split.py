"""Small contract checks; no real hidden evaluation inputs are used."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'installation'), str(ROOT / 'delegation/common'),
                str(ROOT / 'delegation/split/devrev_split')]
from score import numeric_score, evaluate
from packages import build


class SplitContractTests(unittest.TestCase):
    def test_score_contract(self):
        self.assertEqual(numeric_score('{"score": 0}'), 0)
        for output in ('{"score":true}', '{"score":NaN}', '{"score":Infinity}',
                       '{"score":1,"hidden":"not public"}', '[]'):
            with self.assertRaises(ValueError):
                numeric_score(output)
        with self.assertRaisesRegex(ValueError, 'already attempted'):
            evaluate({'state': {'evaluation_attempted': True}, 'binding': {}})

    def test_missing_private_policy_does_not_attempt_or_expose_inputs(self):
        context = {'state': {}, 'binding': {}}
        with patch('score.private_evaluator', side_effect=PermissionError('private path/inputs')):
            with self.assertRaisesRegex(ValueError, 'Private evaluation unavailable') as result:
                evaluate(context)
        self.assertNotIn('private path/inputs', str(result.exception))
        self.assertEqual(context['state'], {})

    def test_rebuilt_installer_removes_old_routing_only(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'installer'
            old = [target / 'delegation' / path for path in
                   ('common/router.py', 'split/controller.py', 'split/SKILL.md')]
            for path in old:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('obsolete')
            kept = target / 'delegation' / 'common' / 'local-settings.json'
            kept.write_text('{}')
            build('installation', target)
            self.assertTrue(all(not path.exists() for path in old))
            self.assertTrue(kept.exists())
