"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from inventory.decode import decode_rows
from inventory.encode import encode_rows


class Oracle(unittest.TestCase):
    def test_special_fields_round_trip(self):
        columns = ["sku", "note"]
        rows = [{"sku": "a,b", "note": 'say "hi"\nnext'}]
        text = encode_rows(columns, rows)
        self.assertEqual(decode_rows(text, columns), rows)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(decode_rows(encode_rows(columns, []), columns), [])

    def test_bad_header_and_quote_raise(self):
        columns = ["sku", "note"]
        with self.assertRaises(ValueError):
            decode_rows("sku,name\n", columns)
        with self.assertRaises(ValueError):
            decode_rows('sku,note\n"unterminated,x\n', columns)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
