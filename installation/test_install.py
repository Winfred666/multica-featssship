import unittest
from unittest.mock import patch

from install import execute, validate


class AgentReuseTests(unittest.TestCase):
    def config(self):
        return {'repository': 'repo', 'directions': [{'name': 'work', 'scope': '.',
                'test_command': 'git diff --check', 'questions': ['Works?']}],
                'delegator': {'id': 'worker'}, 'developer': {'id': 'worker'},
                'reviewer': {'id': 'reviewer'}}

    def test_reuse_in_validation_and_execution(self):
        config = self.config()
        issue = {'id': 'install', 'project_id': 'project'}
        with patch('install.repo_root'), patch('install.check_repo'), \
             patch('install.main_root', return_value={'id': 'main', 'assignee_id': 'worker'}), \
             patch('install.agent', side_effect=lambda config, role, issue: config[role]['id']), \
             patch('install.deploy', return_value='run'):
            result = execute(config, issue, {'main_issue_id': 'main'}, lambda: None)
        self.assertEqual((result['root_issue_id'], result['developer_id'], result['reviewer_id']),
                         ('main', 'worker', 'reviewer'))

    def test_reviewer_must_be_independent_in_validation_and_execution(self):
        for role in ('delegator', 'developer'):
            config = self.config()
            config['delegator']['id'], config['developer']['id'] = 'main', 'dev'
            config['reviewer']['id'] = config[role]['id']
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, 'distinct'):
                validate(config)
        config = self.config()
        with patch('install.repo_root'), patch('install.check_repo'), \
             patch('install.main_root', return_value={'id': 'main', 'assignee_id': 'reviewer'}), \
             patch('install.agent', side_effect=lambda config, role, issue: config[role]['id']), \
             patch('install.deploy') as deploy, self.assertRaisesRegex(ValueError, 'distinct'):
            execute(config, {'id': 'install', 'project_id': 'project'}, {}, lambda: None)
        deploy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
