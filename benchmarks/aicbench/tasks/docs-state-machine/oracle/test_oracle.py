"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



import hashlib

FROZEN = {
        "workflow.py": "2511f726fffa6f59391f1bed50c2f0e033bb74c0742e2269759e5b7e63d8ab0f",
}


class Oracle(unittest.TestCase):
    def test_bullets_match_the_table(self):
        for relative, digest in FROZEN.items():
            digest_now = hashlib.sha256((WORKSPACE / relative).read_bytes()).hexdigest()
            self.assertEqual(digest_now, digest)
        import workflow
        expected = {f"{src} -> {dst}" for src, destinations in workflow.TRANSITIONS.items() for dst in destinations}
        document = (WORKSPACE / "docs" / "states.md").read_text(encoding="utf-8")
        bullets = []
        for line in document.splitlines():
            if line.startswith("#"):
                continue
            if line.strip() == "":
                continue
            self.assertTrue(line.startswith("- "), line)
            bullets.append(line[2:])
        self.assertEqual(set(bullets), expected)
        self.assertEqual(len(bullets), len(expected))


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
