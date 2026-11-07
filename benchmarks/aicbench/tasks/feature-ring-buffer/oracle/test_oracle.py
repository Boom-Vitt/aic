"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from buffers.queue import Queue
from buffers.ring import RingBuffer


class Oracle(unittest.TestCase):
    def test_ring_and_queue(self):
        queue = Queue()
        queue.put("a")
        queue.put("b")
        self.assertEqual(queue.get(), "a")
        with self.assertRaises(IndexError):
            Queue().get()
        with self.assertRaises(ValueError):
            RingBuffer(0)
        ring = RingBuffer(2)
        ring.append("a")
        ring.append("b")
        ring.append("c")
        self.assertEqual(ring.capacity, 2)
        self.assertEqual(ring.to_list(), ["b", "c"])
        self.assertEqual(len(ring), 2)
        self.assertEqual(ring.pop(), "b")
        self.assertEqual(ring.to_list(), ["c"])
        ring.pop()
        with self.assertRaises(IndexError):
            ring.pop()

    def test_added_unit_tests_pass(self):
        import subprocess
        import sys
        path = WORKSPACE / "tests" / "test_ring.py"
        self.assertTrue(path.is_file(), "add tests/test_ring.py")
        text = path.read_text(encoding="utf-8")
        self.assertIn('append', text)
        self.assertIn("self.assert", text)
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "tests.test_ring"],
            cwd=WORKSPACE,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
