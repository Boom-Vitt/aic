"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from safepath.join import join_under
from safepath.policy import is_within


class Oracle(unittest.TestCase):
    def test_component_boundary_and_escape(self):
        self.assertTrue(is_within("/srv/app", "/srv/app"))
        self.assertTrue(is_within("/srv/app", "/srv/app/data"))
        self.assertTrue(is_within("/srv/app", "/srv/app/./data"))
        self.assertFalse(is_within("/srv/app", "/srv/app-secret"))
        self.assertFalse(is_within("/srv/app", "/srv/application"))
        self.assertFalse(is_within("/srv/app", "srv/app"))
        self.assertEqual(join_under("/srv/app", "data/file.txt"), "/srv/app/data/file.txt")
        self.assertEqual(join_under("/srv/app", "sub/../data"), "/srv/app/data")
        with self.assertRaises(ValueError):
            join_under("/srv/app", "/etc/passwd")
        with self.assertRaises(ValueError):
            join_under("/srv/app", "../secret")
        with self.assertRaises(ValueError):
            join_under("/srv/app", "")


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
