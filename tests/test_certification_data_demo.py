"""Offline tests: run with unittest discovery, avoiding project conftest mocks."""
import sqlite3
import unittest
from scripts.certification.data_demo import MACHINES, run_demo


class DataDemoTests(unittest.TestCase):
    def test_totals_normalization_and_provenance(self):
        result = run_demo()
        self.assertTrue(result['synthetic'])
        self.assertEqual(result['input_rows'], 5)
        self.assertEqual(result['imported_rows'], 3)
        self.assertEqual([r['reason'] for r in result['rejections']], ['invalid_record', 'exact_duplicate'])
        self.assertEqual(result['site_payload'], [{'id': 1, 'name': 'Synthetic A', 'timezone': 'UTC', 'machine_count': 2}])
        self.assertEqual(result, run_demo())

    def test_site_scope(self):
        self.assertEqual(run_demo(site_id=2)['site_payload'][0]['machine_count'], 1)
        self.assertEqual(run_demo(site_id=99)['site_payload'], [])
        self.assertEqual(run_demo(site_id='1 OR 1=1')['site_payload'], [])

    def test_empty_site_preserved_by_left_join(self):
        self.assertEqual(run_demo('id,site_id,erp_ref,name\n')['site_payload'][0]['machine_count'], 0)

    def test_foreign_key_and_conflicting_identity_fail_closed(self):
        for row in ('5,99,SYN-05,Unknown site\n', '1,1,OTHER,Conflict\n'):
            with self.assertRaises(sqlite3.IntegrityError):
                run_demo(MACHINES + row)

    def test_existing_api_contract(self):
        from backend.app.schemas import Site
        for payload in run_demo()['site_payload']:
            self.assertEqual(Site(**payload).machine_count, 2)
