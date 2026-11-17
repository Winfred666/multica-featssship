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
from router import roles
from score import numeric_score, evaluate
from packages import build


class SplitContractTests(unittest.TestCase):
    def test_default_router_and_score_contract(self):
        self.assertEqual(roles({}), ('delegation', 'feature'))
        self.assertEqual(roles({'develop_reviewer_split': False}), roles({}))
        self.assertEqual(roles({'develop_reviewer_split': True}), ('split-delegation', 'split-feature'))
        with self.assertRaises(ValueError):
            roles({'develop_reviewer_split': 'false'})
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

    def test_fixed_project_context_is_only_in_split_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            normal = build('delegation', Path(directory) / 'normal')
            split = build('split-delegation', Path(directory) / 'split')
            self.assertFalse((normal / 'PROJECT.md').exists())
            self.assertIn('ontology module dictionary', (split / 'PROJECT.md').read_text())
            self.assertTrue(json.loads((normal / 'config.json').read_text())['DEBUG'])
            self.assertTrue(json.loads((split / 'config.json').read_text())['DEBUG'])
