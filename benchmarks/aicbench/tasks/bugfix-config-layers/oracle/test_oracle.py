"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from layers.load import load_config
from layers.merge import merge


class Oracle(unittest.TestCase):
    def test_nested_user_values_win_without_mutation(self):
        base = {"a": {"b": 1, "c": 2}, "items": [1], "flag": True}
        overlay = {"a": {"b": 9}, "items": [2, 3], "flag": None}
        original_base = {"a": {"b": 1, "c": 2}, "items": [1], "flag": True}
        merged = merge(base, overlay)
        self.assertEqual(merged, {"a": {"b": 9, "c": 2}, "items": [2, 3], "flag": None})
        self.assertEqual(base, original_base)
        self.assertEqual(overlay["items"], [2, 3])
        defaults = {"service": {"host": "local", "port": 80}, "name": "app"}
        user = {"service": {"port": 443}}
        self.assertEqual(load_config(defaults, user), {"service": {"host": "local", "port": 443}, "name": "app"})
        self.assertEqual(defaults["service"]["port"], 80)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
