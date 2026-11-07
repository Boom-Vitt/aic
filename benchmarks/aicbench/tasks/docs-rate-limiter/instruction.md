Write `docs/rate-limiter.md` from `bucket.py`. Do not change any Python file.

Read the public class and document it for a maintainer:
- Name the class and every constructor parameter, excluding `self`.
- State that `acquire` returns True when the requested tokens are taken, using the phrase `returns True`.
- State that `acquire` returns False when the bucket does not hold enough tokens, using the phrase `returns False`.
- State the default amount with the exact phrase `default amount is N`, where N is the integer default in the method signature.
- State that stored tokens never exceed capacity, using the phrase `never exceed capacity`.
- Do not describe the bucket as sleeping, blocking, or waiting. Those words must not appear.

Acceptance: the Markdown states only behavior that the implementation has, and the Python bytes are unchanged.
