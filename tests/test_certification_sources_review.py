"""Pure regression tests: no Docker, Spark or DuckDB required."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import subprocess
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.certification.sources import analytics, database, sandbox, spark
from scripts.certification.sources.window import validate_window

START = '2026-09-01T00:00:00Z'
END = '2026-09-02T00:00:00Z'


class Review(unittest.TestCase):
    def test_windows_rejected_before_io_without_optional_dependencies(self):
        invalid = [(START, START), (END, START), (None, END), (START, None),
                   ('2026-09-01', END), (START, '2026-09-02T00:00:00'),
                   ('bad', END), ('2026-09-01T02:00:00+02:00', START)]
        with patch.dict('sys.modules', {'duckdb': None}), patch.object(analytics, 'Path', side_effect=AssertionError('I/O')):
            for start, end in invalid:
                for adapter, args in [(analytics.extract, ('missing.jsonl',)),
                                      (database.extract, (None,)),
                                      (spark.extract, (None, 'partition'))]:
                    with self.subTest(adapter=adapter.__module__, start=start, end=end):
                        with self.assertRaisesRegex(ValueError, '^invalid_window$'):
                            adapter(*args, 1, start, end)

    def test_offset_window_canonicalized(self):
        expected = (datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 2, tzinfo=timezone.utc))
        self.assertEqual(validate_window('2026-09-01T02:00:00+02:00', '2026-09-01T20:00:00-04:00'), expected)
        self.assertEqual(validate_window(*expected), expected)

    def sandbox_failure(self, foreign=False, missing=False):
        def command(*args):
            if args[0] == 'run':
                raise subprocess.CalledProcessError(1, 'docker run')
            if args[0] == 'inspect':
                if missing:
                    raise subprocess.CalledProcessError(1, 'docker inspect')
                return 'foreign' if foreign else args[-1]
            return ''
        with patch.dict('sys.modules', {'psycopg': SimpleNamespace()}), patch.object(sandbox, 'command', side_effect=command) as calls:
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                sandbox.run()
            self.assertEqual(caught.exception.cmd, 'docker run')
            self.assertTrue(any(c.args[0] == 'inspect' for c in calls.call_args_list))
            removals = [c.args for c in calls.call_args_list if c.args[0] == 'rm']
            self.assertEqual(len(removals), 0 if foreign or missing else 1)

    def test_failed_run_created_owned_container_removed(self):
        self.sandbox_failure()

    def test_failed_run_foreign_container_preserved(self):
        self.sandbox_failure(foreign=True)

    def test_failed_run_missing_container_preserves_original_error(self):
        self.sandbox_failure(missing=True)

    def check_spark(self, fail=False, concurrent=False):
        barrier = threading.Barrier(2) if concurrent else None
        children = []
        caller = Mock()
        caller.views = {'certification_cycles': 'caller-data'}
        caller.timezone = 'Europe/Paris'

        def new_session():
            child = Mock()
            child.views = {}
            child.conf.set.side_effect = lambda key, value: setattr(child, 'timezone', value)
            child.read.parquet.return_value.createOrReplaceTempView.side_effect = lambda name: child.views.update({name: 'fixture'})
            child.catalog.dropTempView.side_effect = lambda name: child.views.pop(name, None)

            def sql(*args, **kwargs):
                self.assertEqual(child.timezone, 'UTC')
                self.assertEqual(child.views, {'certification_cycles': 'fixture'})
                self.assertEqual(kwargs['args']['from_utc'], '2026-09-01T00:00:00+00:00')
                if barrier:
                    barrier.wait(timeout=5)
                if fail:
                    raise RuntimeError('query_failed')
                return SimpleNamespace(collect=lambda: [])
            child.sql.side_effect = sql
            children.append(child)
            return child

        caller.newSession.side_effect = new_session
        def run():
            return spark.extract(caller, 'approved', 1, '2026-09-01T02:00:00+02:00', END)
        if fail:
            with self.assertRaisesRegex(RuntimeError, 'query_failed'):
                run()
        elif concurrent:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(run) for _ in range(2)]
                self.assertEqual([f.result(timeout=10) for f in futures], [[], []])
        else:
            self.assertEqual(run(), [])
        self.assertEqual(caller.views, {'certification_cycles': 'caller-data'})
        self.assertEqual(caller.timezone, 'Europe/Paris')
        caller.conf.set.assert_not_called()
        caller.catalog.dropTempView.assert_not_called()
        caller.stop.assert_not_called()
        self.assertEqual(len(children), 2 if concurrent else 1)
        for child in children:
            self.assertEqual(child.views, {})
            child.stop.assert_not_called()

    def test_spark_caller_preserved_success(self):
        self.check_spark()

    def test_spark_caller_preserved_exception(self):
        self.check_spark(fail=True)

    def test_spark_concurrent_isolated_views(self):
        self.check_spark(concurrent=True)
