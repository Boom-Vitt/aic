"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from ledger.parse import parse_amount
from ledger.totals import net_cents


class Oracle(unittest.TestCase):
    def test_signed_examples(self):
        self.assertEqual(parse_amount("12.50"), 1250)
        self.assertEqual(parse_amount("-4.00"), -400)
        self.assertEqual(parse_amount("$1,234.56"), 123456)
        self.assertEqual(parse_amount("(12.50)"), -1250)
        self.assertEqual(parse_amount("($1,234.56)"), -123456)
        self.assertEqual(parse_amount("  -4.00  "), -400)
        self.assertEqual(net_cents(["10.00", "(3.00)", ""]), 700)
        self.assertEqual(net_cents(["10.00", "  ", "-2.50"]), 750)

    def test_invalid_tokens_raise(self):
        for token in ("1.2", "12", "(12.50", "12,34.56", "", "-(4.00)", "12.345"):
            with self.subTest(token=token):
                with self.assertRaises(ValueError):
                    parse_amount(token)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
