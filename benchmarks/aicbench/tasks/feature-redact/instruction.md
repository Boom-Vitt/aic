Add `logs.redact.redact(text, secrets)`. Keep `logs.format.format_event("login", "ok")` equal to `"login: ok"`.

`text` is a string and `secrets` is a list of strings. Skip empty secrets. A non-string secret or a non-string text raises `TypeError`. Replace matches with the exact token `[REDACTED]`. At each position, prefer the longest secret that matches there, and continue after that match so a shorter secret does not consume part of a longer one. Matching is case sensitive. `redact("abcdef", ["abc", "abcdef"])` is `"[REDACTED]"`. `redact("a abc a", ["abc"])` is `"a [REDACTED] a"`. `redact("ABC", ["abc"])` is `"ABC"`. `redact("x", [""])` is `"x"`.

Add `tests/__init__.py` and `tests/test_redact.py` containing `[REDACTED]`, runnable as `python -m unittest tests.test_redact`.

Acceptance: longer secrets win, case is preserved, and the formatter is unchanged.
