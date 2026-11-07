"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



import billing


class Oracle(unittest.TestCase):
    def test_package_replaces_the_module(self):
        self.assertFalse((WORKSPACE / "billing.py").exists())
        for name in ("money.py", "tax.py", "invoice.py", "__init__.py"):
            self.assertTrue((WORKSPACE / "billing" / name).is_file())
        self.assertEqual(billing.tax_cents(10, 750), 1)
        self.assertEqual(billing.line_total(250, 2), 500)
        self.assertEqual(billing.total([{"unit_cents": 250, "qty": 2}], 50, 1000), 600)
        with self.assertRaises(ValueError):
            billing.total([{"unit_cents": 10, "qty": 1}], -1, 0)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
