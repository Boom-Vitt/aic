"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



import ast
import hashlib

FROZEN = {
        "bucket.py": "abb986043b9bbe8ecee4357b5236f35afe61b250b7c460929d0b5273ec6f0ece",
}


def _digest(relative):
    return hashlib.sha256((WORKSPACE / relative).read_bytes()).hexdigest()


class Oracle(unittest.TestCase):
    def test_documentation_matches_the_class(self):
        for relative, digest in FROZEN.items():
            self.assertEqual(_digest(relative), digest)
        source = (WORKSPACE / "bucket.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        self.assertEqual(len(classes), 1)
        bucket = classes[0]
        initializer = next(node for node in bucket.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        acquire = next(node for node in bucket.body if isinstance(node, ast.FunctionDef) and node.name == "acquire")
        parameters = [arg.arg for arg in initializer.args.args if arg.arg != "self"]
        default = acquire.args.defaults[-1]
        self.assertIsInstance(default, ast.Constant)
        document = (WORKSPACE / "docs" / "rate-limiter.md").read_text(encoding="utf-8")
        self.assertIn(bucket.name, document)
        for name in parameters:
            self.assertIn(name, document)
        self.assertIn("returns True", document)
        self.assertIn("returns False", document)
        self.assertIn(f"default amount is {default.value}", document)
        self.assertIn("never exceed capacity", document)
        lowered = document.casefold()
        for banned in ("sleep", "block", "wait"):
            self.assertNotIn(banned, lowered)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
