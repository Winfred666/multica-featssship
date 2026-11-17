"""Small contract checks; no real hidden evaluation inputs are used."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'installation'), str(ROOT / 'delegation/common'),
                str(ROOT / 'delegation/split/devrev_split')]
from router import roles
from score import numeric_score, evaluate


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
