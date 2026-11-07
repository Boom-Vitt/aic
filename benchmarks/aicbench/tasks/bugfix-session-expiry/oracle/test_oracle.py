"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from sessions.store import valid
from sessions.tokens import refresh


class Oracle(unittest.TestCase):
    def test_expiry_is_exclusive_and_refresh_starts_from_now(self):
        self.assertFalse(valid({"expires_at": 10, "revoked": False}, 10))
        self.assertTrue(valid({"expires_at": 10, "revoked": False}, 9))
        self.assertFalse(valid({"expires_at": 10, "revoked": True}, 9))
        session = {"id": "s", "expires_at": 100, "revoked": False}
        updated = refresh(session, 10, 5)
        self.assertEqual(updated["expires_at"], 15)
        self.assertFalse(updated["revoked"])
        self.assertEqual(session["expires_at"], 100)
        with self.assertRaises(PermissionError):
            refresh({"id": "s", "expires_at": 100, "revoked": True}, 10, 5)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
