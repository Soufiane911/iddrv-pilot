import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/certification/rgpd/synthetic_purge.py'
spec = importlib.util.spec_from_file_location('c4_purge', SCRIPT)
purge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(purge)


class SyntheticPurgeTests(unittest.TestCase):
    def setUp(self):
        self.exercise = purge.SyntheticExercise()
        self.policy = purge.example_policy()

    def tearDown(self):
        self.exercise.close()

    def test_dry_run_immutable_and_counts(self):
        before = self.exercise.snapshot()
        writes = []
        self.exercise._db.set_trace_callback(writes.append)
        report = self.exercise.run(self.policy)
        self.assertEqual(before, self.exercise.snapshot())
        self.assertEqual((report['candidate_sessions'], report['candidate_files'], report['held_sessions']), (1, 1, 1))
        self.assertFalse(any(s.startswith(('DELETE', 'INSERT', 'UPDATE')) for s in writes))

    def test_exact_execution_other_sites_and_protected_audit(self):
        before = self.exercise.snapshot()
        result = self.exercise.run(self.policy, execute=True, confirmation=purge.CONFIRMATION)
        after = self.exercise.snapshot()
        self.assertEqual(result['after_counts']['import_sessions'], 5)
        self.assertEqual(after['import_sessions'], [r for r in before['import_sessions'] if r[0] != 'old'])
        self.assertEqual(after['import_session_files'], [r for r in before['import_session_files'] if r[1] != 'old'])
        for table in ('users', 'sites', 'semantic_mapping_decisions'):
            self.assertEqual(before[table], after[table])
        self.assertEqual(self.exercise._db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(self.exercise.run(self.policy)['candidate_sessions'], 0)

    def test_rollback_on_error(self):
        before = self.exercise.snapshot()
        with self.assertRaises(RuntimeError):
            self.exercise.run(self.policy, execute=True, confirmation=purge.CONFIRMATION, fail_after_files=True)
        self.assertEqual(before, self.exercise.snapshot())

    def test_fk_rejects_orphan(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.exercise._db.execute("INSERT INTO import_session_files VALUES ('bad','missing','synthetic')")
        self.exercise._db.rollback()

    def test_cross_session_decision_reference_preserved(self):
        self.exercise._db.execute("INSERT INTO semantic_mapping_decisions VALUES ('cross','other-site','old-file')")
        self.exercise._db.commit()
        report = self.exercise.run(self.policy, execute=True, confirmation=purge.CONFIRMATION)
        self.assertEqual(report['candidate_sessions'], 0)
        self.assertEqual(report['held_sessions'], 2)

    def test_incomplete_and_unknown_policies_fail_closed(self):
        before = self.exercise.snapshot()
        for key in self.policy:
            bad = dict(self.policy)
            del bad[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.exercise.run(bad)
        for key, value in [('site_id', True), ('site_id', '1 OR 1=1'), ('site_id', 3),
                           ('status', "failed'; DROP TABLE users;--"), ('context', 'prod'),
                           ('decision_policy', 'erase'), ('sql', 'DELETE FROM users')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.exercise.run(dict(self.policy, **{key: value}))
        self.assertEqual(before, self.exercise.snapshot())

    def test_dates_and_timezone_boundaries(self):
        self.assertEqual(purge.utc('2026-01-01T00:00:00Z'), purge.utc('2026-01-01T00:00:00+00:00'))
        for value in ['2026-02-30T00:00:00Z', '2026-01-01', '2026-01-01T00:00:00',
                      '2026-01-01T01:00:00+01:00', '2026-01-01T00:00:00-00:00', None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                purge.utc(value)
        self.policy['cutoff_utc'] = '2026-01-01T00:00:00.000001Z'
        self.assertEqual(self.exercise.run(self.policy)['candidate_sessions'], 2)
        self.policy['cutoff_utc'] = self.policy['as_of_utc']
        with self.assertRaises(ValueError):
            self.exercise.run(self.policy)

    def test_confirmation_required(self):
        with self.assertRaises(ValueError):
            self.exercise.run(self.policy, execute=True)

    def test_outputs_no_content_and_cli_injection_redacted(self):
        output = json.dumps(self.exercise.run(self.policy))
        self.assertNotIn('synthetic.xlsx', output)
        self.assertNotIn('synthetic-user', output)
        self.assertNotIn('held-decision', output)
        result = subprocess.run([sys.executable, str(SCRIPT), '--policy-json', '{SECRET_SENTINEL'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('SECRET_SENTINEL', result.stdout + result.stderr)


class SourceInventoryTests(unittest.TestCase):
    def test_all_declared_tables_and_sources_still_match(self):
        spec = importlib.util.spec_from_file_location('c4_inventory', ROOT / 'scripts/certification/rgpd/schema_inventory.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        saved = json.loads((ROOT / 'docs/certification/rgpd-c4/sql-source-index.json').read_text())
        self.assertEqual(saved, module.inventory())
        self.assertEqual(len(saved['tables']), 56)
        self.assertEqual(len(saved['sources']), 24)

    def test_document_local_links_exist(self):
        import re
        folder = ROOT / 'docs/certification/rgpd-c4'
        for document in folder.glob('*.md'):
            for target in re.findall(r'\]\(([^)]+)\)', document.read_text()):
                if '://' not in target and not target.startswith('#'):
                    self.assertTrue((document.parent / target.split('#')[0]).exists(), (document, target))


if __name__ == '__main__':
    unittest.main()
