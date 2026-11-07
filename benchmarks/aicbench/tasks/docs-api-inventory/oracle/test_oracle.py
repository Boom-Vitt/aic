"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



import ast
import hashlib

FROZEN = {
        "stats/__init__.py": "4ed4ce8f711bbed8aa179f77b5efb287337beb128231faf5a3c0be956766f95e",
}


class Oracle(unittest.TestCase):
    def test_signatures_match_public_functions(self):
        for relative, digest in FROZEN.items():
            digest_now = hashlib.sha256((WORKSPACE / relative).read_bytes()).hexdigest()
            self.assertEqual(digest_now, digest)
        source = (WORKSPACE / "stats" / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")]
        document = (WORKSPACE / "docs" / "api.md").read_text(encoding="utf-8")
        headings = [line[3:] for line in document.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, [node.name for node in functions])
        for node in functions:
            names = [arg.arg for arg in node.args.args if arg.arg != "self"]
            signature = "signature: " + node.name + "(" + ", ".join(names) + ")"
            self.assertIn(signature, document)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
