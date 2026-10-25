"""No-database fixtures for coordinator API access checks."""

import importlib.util
from pathlib import Path
import sys
import unittest


DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location('verify_coordinator_access',
                                               DIRECTORY / 'verify-coordinator-access.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AccessTest(unittest.TestCase):
    def test_expected_read_only_requests(self):
        calls = []

        class API:
            def __init__(self, profile):
                self.cluster = profile['cluster']

            def request(self, method, path):
                calls.append((self.cluster, method, path))
                if '/leases/' in path:
                    return {'metadata': {'name': 'liora-backup-cycle'}}
                return {'kind': 'BackupList', 'items': []}

        MODULE.verify({'clusters': {'nonprod': {'cluster': 'nonprod'},
                                   'prod': {'cluster': 'prod'}}}, API)
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(method == 'GET' for _, method, _ in calls))
        self.assertIn(('nonprod', 'GET', '/apis/postgresql.cnpg.io/v1/namespaces/app-dev/backups'), calls)

    def test_wrong_response_stops(self):
        class API:
            def __init__(self, profile):
                pass

            def request(self, method, path):
                return {'kind': 'SecretList'}

        with self.assertRaisesRegex(ValueError, 'BackupList'):
            MODULE.verify({'clusters': {'nonprod': {}, 'prod': {}}}, API)


if __name__ == '__main__':
    unittest.main()
