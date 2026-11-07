Add `timekit.duration.parse_duration(text) -> int` seconds. Keep `timekit.stamp.format_hhmmss(3661)` equal to `"01:01:01"`.

A duration is a nonempty string with optional hours, minutes, and seconds in that order. Each present unit appears once, uses the suffix `h`, `m`, or `s`, and has a nonnegative integer with no leading zero except the number 0 itself. No spaces or signs are allowed. At least one unit is required.
`parse_duration("1h30m")` is `5400`, `"1h30m15s"` is `5415`, `"90s"` is `90`, `"1h"` is `3600`, `"1m"` is `60`, and `"0s"` is `0`.
`"01h"`, `"1h1h"`, `"1s1h"`, `""`, `"1"`, and `"1h "` raise `ValueError`.

Add `tests/__init__.py` and `tests/test_duration.py` asserting `1h30m`, runnable as `python -m unittest tests.test_duration`.

Acceptance: the parser accepts only the ordered form above and the existing stamp helper is unchanged.
