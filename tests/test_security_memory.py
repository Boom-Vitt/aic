"""Bounded explicit memory ingestion through the public reference-note APIs."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/aic/scripts'))

from aiclib import memory
from aiclib.safety import AICError, canonical_json


NOTE_BYTES = 1024 * 1024
NOTE_ENTRIES = 256
TOTAL_BYTES = 8 * 1024 * 1024


class SecurityMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'README.txt'
        self.source.write_bytes(b'Local observed evidence.\n')
        self.source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.unrelated = self.root / 'unrelated.txt'
        self.unrelated.write_bytes(b'Unrelated data must remain untouched.\n')
        self.folder = self.root / '.aic/memory/notes'

    def _candidate(self, index):
        return dict(claim=f'Observed local fact {index}.', source='README.txt',
                    source_date='2026-11-01', checked_at='2026-11-06',
                    scope=['README.txt'], status='observed')

    def _note_bytes(self, candidate):
        return canonical_json(dict(schema_version=1, kind='aic-scoped-reference',
                                   candidate=candidate, source_sha256=self.source_hash))

    def _sized_candidate(self, size, index, fill='x'):
        candidate = self._candidate(index)
        remaining = size - len(self._note_bytes(candidate))
        self.assertGreaterEqual(remaining, 0)
        repeats, remainder = divmod(remaining, len(fill.encode('utf-8')))
        candidate['claim'] += fill * repeats + 'x' * remainder
        self.assertEqual(len(self._note_bytes(candidate)), size)
        return candidate

    def _write_note(self, candidate):
        # Construct the real immutable format directly to avoid quadratic promotion setup.
        raw = self._note_bytes(candidate)
        digest = hashlib.sha256(raw).hexdigest()
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f'{digest}.json'
        with path.open('xb') as stream:
            stream.write(raw)
        return path

    def _snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def _assert_complete_local_references(self, expected_paths):
        notes = memory.read_notes(self.root)
        self.assertEqual(len(notes), len(expected_paths))
        self.assertEqual({item['path'] for item in notes},
                         {path.relative_to(self.root).as_posix() for path in expected_paths})
        for item in notes:
            self.assertEqual(item['authority'], 'reference-data-only')
            self.assertEqual(item['source_verification'], 'local-hash')
            self.assertFalse(item['stale'])
            self.assertEqual(item['note']['source_sha256'], self.source_hash)
        return notes

    def test_reader_rejects_one_byte_oversized_canonical_hash_matching_note(self):
        legitimate = memory.promote(self.root, self._candidate('legitimate'), approved=True)
        candidate = self._sized_candidate(NOTE_BYTES + 1, 'oversized', fill='é')
        self._write_note(candidate)
        before = self._snapshot()

        with self.assertRaises(AICError):
            memory.read_notes(self.root)

        self.assertEqual(self._snapshot(), before)
        self.assertIn(legitimate['path'], before)

    def test_promotion_rejects_one_byte_oversized_note_without_mutation(self):
        legitimate = memory.promote(self.root, self._candidate('legitimate'), approved=True)
        candidate = self._sized_candidate(NOTE_BYTES + 1, 'oversized', fill='é')
        before = self._snapshot()

        with self.assertRaises(AICError):
            memory.promote(self.root, candidate, approved=True)

        self.assertEqual(self._snapshot(), before)
        self._assert_complete_local_references([self.root / legitimate['path']])

    def test_maximum_size_note_roundtrips_idempotently_and_retains_source_authority(self):
        candidate = self._sized_candidate(NOTE_BYTES, 'maximum', fill='é')
        first = memory.promote(self.root, candidate, approved=True)
        path = self.root / first['path']
        before = self._snapshot()
        before_stat = path.stat()

        second = memory.promote(self.root, candidate, approved=True)

        self.assertEqual(first['status'], 'promoted')
        self.assertEqual(second['status'], 'unchanged')
        self.assertEqual(first['path'], second['path'])
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(path.stat().st_mtime_ns, before_stat.st_mtime_ns)
        notes = self._assert_complete_local_references([path])
        self.assertEqual(notes[0]['note']['candidate'], candidate)
        self.source.write_bytes(b'Changed local evidence.\n')
        stale = memory.read_notes(self.root)[0]
        self.assertTrue(stale['stale'])
        self.assertEqual(stale['authority'], 'reference-data-only')
        self.assertEqual(stale['note']['source_sha256'], self.source_hash)
        self.assertEqual(path.read_bytes(), before[first['path']])

    def test_reader_rejects_257_valid_notes_without_returning_a_truncated_collection(self):
        for index in range(NOTE_ENTRIES + 1):
            self._write_note(self._candidate(index))
        before = self._snapshot()

        with self.assertRaises(AICError):
            memory.read_notes(self.root)

        self.assertEqual(self._snapshot(), before)

    def test_promotion_rejects_257th_note_preserving_existing_notes(self):
        paths = [self._write_note(self._candidate(index)) for index in range(NOTE_ENTRIES)]
        before = self._snapshot()

        with self.assertRaises(AICError):
            memory.promote(self.root, self._candidate('new-at-capacity'), approved=True)

        self.assertEqual(self._snapshot(), before)
        self._assert_complete_local_references(paths)

    def test_entry_boundary_allows_final_note_and_idempotent_promotion_at_capacity(self):
        paths = [self._write_note(self._candidate(index)) for index in range(NOTE_ENTRIES - 1)]
        candidate = self._candidate('final-at-capacity')
        first = memory.promote(self.root, candidate, approved=True)
        paths.append(self.root / first['path'])
        before = self._snapshot()

        second = memory.promote(self.root, candidate, approved=True)

        self.assertEqual(first['status'], 'promoted')
        self.assertEqual(second['status'], 'unchanged')
        self.assertEqual(first['path'], second['path'])
        self.assertEqual(self._snapshot(), before)
        self._assert_complete_local_references(paths)

    def test_reader_rejects_one_byte_over_aggregate_limit_with_individually_valid_notes(self):
        sizes = [NOTE_BYTES] * 7 + [NOTE_BYTES - 4095, 4096]
        self.assertEqual(sum(sizes), TOTAL_BYTES + 1)
        for index, size in enumerate(sizes):
            self._write_note(self._sized_candidate(size, index))
        before = self._snapshot()

        with self.assertRaises(AICError):
            memory.read_notes(self.root)

        self.assertEqual(self._snapshot(), before)

    def test_promotion_rejects_aggregate_overflow_without_writing_or_removing_notes(self):
        paths = [self._write_note(self._sized_candidate(NOTE_BYTES, index)) for index in range(8)]
        before = self._snapshot()

        with self.assertRaises(AICError):
            memory.promote(self.root, self._candidate('aggregate-overflow'), approved=True)

        self.assertEqual(self._snapshot(), before)
        self._assert_complete_local_references(paths)

    def test_aggregate_boundary_allows_final_note_and_idempotent_promotion(self):
        paths = [self._write_note(self._sized_candidate(NOTE_BYTES, index)) for index in range(7)]
        candidate = self._sized_candidate(NOTE_BYTES, 'final-aggregate')
        first = memory.promote(self.root, candidate, approved=True)
        paths.append(self.root / first['path'])
        self.assertEqual(sum(path.stat().st_size for path in paths), TOTAL_BYTES)
        before = self._snapshot()

        second = memory.promote(self.root, candidate, approved=True)

        self.assertEqual(first['status'], 'promoted')
        self.assertEqual(second['status'], 'unchanged')
        self.assertEqual(first['path'], second['path'])
        self.assertEqual(self._snapshot(), before)
        self._assert_complete_local_references(paths)

    def test_invalid_or_deep_json_is_a_controlled_error_without_mutation(self):
        # This is parser safety coverage, not evidence of a confirmed runtime crash.
        payloads = (b'{', b'\xff', b'[' * 4096 + b'0' + b']' * 4096)
        for index, raw in enumerate(payloads):
            with self.subTest(payload=index):
                case_root = self.root / f'parser-case-{index}'
                folder = case_root / '.aic/memory/notes'
                folder.mkdir(parents=True)
                digest = hashlib.sha256(raw).hexdigest()
                path = folder / f'{digest}.json'
                path.write_bytes(raw)
                before = self._snapshot()

                with self.assertRaises(AICError):
                    memory.read_notes(case_root)

                self.assertEqual(self._snapshot(), before)
