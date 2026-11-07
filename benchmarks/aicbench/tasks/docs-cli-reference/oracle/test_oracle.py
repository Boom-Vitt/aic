"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



import argparse
import hashlib

FROZEN = {
        "cli.py": "49d531981718a3f80dc23ebb6dcd180c2d177be0dfe7e6f3820c035cfc12328b",
}


class Oracle(unittest.TestCase):
    def test_help_strings_are_documented(self):
        for relative, digest in FROZEN.items():
            digest_now = hashlib.sha256((WORKSPACE / relative).read_bytes()).hexdigest()
            self.assertEqual(digest_now, digest)
        import cli
        parser = cli.build_parser()
        document = (WORKSPACE / "docs" / "cli.md").read_text(encoding="utf-8")
        found = False
        for action in parser._actions:
            if not isinstance(action, argparse._SubParsersAction):
                continue
            found = True
            for name, subparser in action.choices.items():
                self.assertIn(name, document)
                for sub_action in subparser._actions:
                    if sub_action.dest == "help" or not sub_action.help:
                        continue
                    self.assertIn(sub_action.help, document)
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
