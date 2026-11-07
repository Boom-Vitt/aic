"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



import checkout
import discounts


class Oracle(unittest.TestCase):
    def test_registry_and_prices(self):
        source = (WORKSPACE / "checkout.py").read_text(encoding="utf-8")
        self.assertIn("REGISTRY", source)
        for code in ("SAVE10", "SAVE20", "FREESHIP"):
            self.assertNotIn(code, source)
            self.assertIn(code, discounts.REGISTRY)
        self.assertEqual(checkout.price(105, 20, "SAVE10"), (94, 20))
        self.assertEqual(checkout.price(100, 25, "SAVE20"), (80, 25))
        self.assertEqual(checkout.price(100, 25, "FREESHIP"), (100, 0))
        self.assertEqual(checkout.price(100, 25, None), (100, 25))
        self.assertEqual(checkout.price(100, 25, ""), (100, 25))
        self.assertEqual(discounts.REGISTRY["SAVE10"](105, 20), (94, 20))
        with self.assertRaises(KeyError):
            checkout.price(100, 25, "NOPE")
        with self.assertRaises(ValueError):
            checkout.price(-1, 0, None)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
