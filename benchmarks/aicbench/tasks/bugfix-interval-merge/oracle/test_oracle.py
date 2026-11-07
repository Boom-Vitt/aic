"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from schedule.agenda import merge_busy
from schedule.intervals import overlaps


class Oracle(unittest.TestCase):
    def test_half_open_overlap_and_merge(self):
        self.assertFalse(overlaps((1, 2), (2, 3)))
        self.assertTrue(overlaps((1, 3), (2, 4)))
        self.assertFalse(overlaps((1, 2), (3, 4)))
        self.assertEqual(merge_busy([(5, 7), (1, 3), (2, 4)]), [(1, 4), (5, 7)])
        self.assertEqual(merge_busy([(1, 2), (2, 3)]), [(1, 2), (2, 3)])
        self.assertEqual(merge_busy([(1, 4)]), [(1, 4)])
        self.assertEqual(merge_busy([]), [])
        with self.assertRaises(ValueError):
            overlaps((1, 1), (0, 2))
        with self.assertRaises(ValueError):
            merge_busy([(True, 2)])


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
