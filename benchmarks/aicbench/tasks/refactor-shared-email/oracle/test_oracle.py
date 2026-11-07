"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



import ast

from orders import normalize_contact
from users import normalize_user


def _calls_helper(path, function_name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != function_name:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Name) and func.id == "require_email":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "require_email":
                return True
    return False


class Oracle(unittest.TestCase):
    def test_shared_normalizer(self):
        self.assertEqual(normalize_user("  User@Example.com  "), "user@example.com")
        self.assertEqual(normalize_contact("  User@Example.com  "), "user@example.com")
        for value in ("admin@localhost", "a@b@c.com", "@example.com", "user@example."):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_user(value)
                with self.assertRaises(ValueError):
                    normalize_contact(value)
        self.assertTrue(_calls_helper(WORKSPACE / "users.py", "normalize_user"))
        self.assertTrue(_calls_helper(WORKSPACE / "orders.py", "normalize_contact"))


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
