"""Restart-safe usage caps and no-replay effects, using only private fixtures."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maintenance.state import State, StateError


class MaintainerStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private' / 'state.sqlite3'

    def open(self):
        state = State(self.path)
        self.addCleanup(state.close)
        return state

    def test_reserved_or_failed_run_still_counts_after_restart(self):
        first = self.open()
        first.reserve('2026-11-06', 'research', 'job-one')
        first.close()
        restarted = self.open()
        with self.assertRaises(StateError):
            restarted.reserve('2026-11-06', 'research', 'job-one')
        restarted.reserve('2026-11-06', 'review', 'job-one')
        with self.assertRaises(StateError):
            restarted.reserve('2026-11-06', 'review', 'job-two')
        self.assertEqual(restarted.runs('2026-11-06'), 2)
        restarted.reserve('2026-11-07', 'research', 'job-two')
        self.assertEqual(restarted.runs('2026-11-07'), 1)

    def test_finished_result_can_resume_without_a_new_run(self):
        state = self.open()
        state.reserve('2026-11-06', 'research', 'job-one')
        state.finish_run('2026-11-06', 'research', 'job-one', {'records': ['approved-artifact']})
        state.close()
        resumed = self.open()
        self.assertEqual(resumed.run_result('job-one', 'research'), {'records': ['approved-artifact']})
        self.assertEqual(resumed.runs('2026-11-06'), 1)

    def test_pending_mutation_is_not_a_license_to_replay(self):
        state = self.open()
        state.begin_effect('job-one', 'create-issue', {'marker': 'owned-marker'})
        state.close()
        resumed = self.open()
        self.assertEqual(resumed.effect('job-one', 'create-issue')['status'], 'pending')
        with self.assertRaises(StateError):
            resumed.begin_effect('job-one', 'create-issue', {'marker': 'owned-marker'})
        resumed.finish_effect('job-one', 'create-issue', {'number': 7})
        self.assertEqual(resumed.effect('job-one', 'create-issue')['result'], {'number': 7})

    def test_only_one_integration_job_can_be_active(self):
        state = self.open()
        state.save_job('job-one', 'collecting', {'date': '2026-11-06'})
        with self.assertRaises(StateError):
            state.save_job('job-two', 'collecting', {'date': '2026-11-06'})
        state.save_job('job-one', 'complete', {'date': '2026-11-06'})
        state.save_job('job-two', 'collecting', {'date': '2026-11-07'})
        self.assertEqual(state.active_job()['key'], 'job-two')

    def test_exclusive_controller_lock_prevents_concurrent_publishers(self):
        first, second = self.open(), self.open()
        with first.exclusive():
            with self.assertRaises(StateError):
                with second.exclusive():
                    self.fail('A second publisher entered the critical section')
        with second.exclusive():
            self.assertEqual(second.runs('2026-11-06'), 0)

    def test_unmanaged_or_linked_state_is_preserved(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b'not an AIC state database')
        before = self.path.read_bytes()
        with self.assertRaises(StateError):
            State(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        linked = self.path.parent / 'linked.sqlite3'
        linked.symlink_to(self.path)
        with self.assertRaises(StateError):
            State(linked)
        self.assertTrue(linked.is_symlink())
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
