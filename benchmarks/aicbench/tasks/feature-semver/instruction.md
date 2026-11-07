Add `versions.semver`. Keep `versions.label.display_label("1.2.3")` equal to `"v1.2.3"`. It does not parse semver; it rejects an empty string.

`parse_version(text)` accepts exactly `major.minor.patch`. Each component is a decimal integer without a sign or a leading zero. `0` is allowed. No `v` prefix and no prerelease suffix are allowed. Anything else raises `ValueError`.
`compare_versions(left, right)` returns `-1`, `0`, or `1` using numeric order, so `1.10.0` is greater than `1.9.0`.
`higher(left, right)` returns the original text of the greater version. Equal versions return the first argument.

Add `tests/__init__.py` and `tests/test_semver.py` mentioning `1.10.0`, runnable as `python -m unittest tests.test_semver`.

Acceptance: leading zeros and short versions are rejected, numeric order is used, and the label helper is unchanged.
