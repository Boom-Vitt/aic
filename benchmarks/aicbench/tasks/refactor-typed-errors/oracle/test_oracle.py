"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from errors import BadType, ConfigError, MissingKey
from loader import load


class Oracle(unittest.TestCase):
    def test_typed_errors_keep_successful_output(self):
        self.assertTrue(issubclass(MissingKey, ConfigError))
        self.assertTrue(issubclass(BadType, ConfigError))
        self.assertEqual(load({"port": 80, "name": "api", "extra": 1}, {"port": int, "name": str}), {"port": 80, "name": "api"})
        with self.assertRaises(MissingKey):
            load({"name": "api"}, {"port": int})
        with self.assertRaises(BadType):
            load({"port": True}, {"port": int})
        with self.assertRaises(BadType):
            load({"name": 4}, {"name": str})


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
