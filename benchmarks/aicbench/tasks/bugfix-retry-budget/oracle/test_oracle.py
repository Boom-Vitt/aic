"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from retry.policy import total_attempts
from retry.runner import run


class Oracle(unittest.TestCase):
    def test_budget_includes_the_first_attempt(self):
        self.assertEqual(total_attempts(0), 1)
        self.assertEqual(total_attempts(2), 3)
        with self.assertRaises(ValueError):
            total_attempts(-1)
        with self.assertRaises(ValueError):
            total_attempts(True)
        calls = []

        def operation():
            calls.append("go")
            if len(calls) < 3:
                raise RuntimeError("again")
            return "ok"

        slept = []
        self.assertEqual(run(operation, max_retries=2, retryable=(RuntimeError,), sleep=slept.append), "ok")
        self.assertEqual(calls, ["go", "go", "go"])
        self.assertEqual(slept, [1, 2])

    def test_non_retryable_does_not_sleep(self):
        calls = []

        def operation():
            calls.append("go")
            raise KeyError("stop")

        slept = []
        with self.assertRaises(KeyError):
            run(operation, max_retries=3, retryable=(RuntimeError,), sleep=slept.append)
        self.assertEqual(calls, ["go"])
        self.assertEqual(slept, [])

    def test_exhausted_retry_raises_the_last_error(self):
        calls = []

        def operation():
            calls.append("go")
            raise RuntimeError("last")

        slept = []
        with self.assertRaisesRegex(RuntimeError, "last"):
            run(operation, max_retries=1, retryable=(RuntimeError,), sleep=slept.append)
        self.assertEqual(len(calls), 2)
        self.assertEqual(slept, [1])


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
