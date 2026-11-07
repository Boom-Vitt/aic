Fix the ledger so signed amounts and totals follow the contract below. Two modules are wrong: parsing and totaling. Change only this workspace.

`ledger.parse.parse_amount(token)` returns integer cents.
A token may have surrounding whitespace. A leading `$` is optional. Thousands separators are commas in groups of three, as in `$1,234.56`. Exactly two decimal digits are required.
A leading `-` means negative. Accounting parentheses also mean negative, including an optional dollar sign inside them: `(12.50)` and `($1,234.56)` are negative. Parentheses and a leading minus cannot be combined.
`1.2`, `12`, `(12.50`, `12,34.56`, and an empty token raise `ValueError`.

`ledger.totals.net_cents(lines)` sums `parse_amount` for every line that is not empty after stripping. Blank lines are ignored. The total is signed. Do not sum absolute values.
`net_cents(["10.00", "(3.00)", ""])` is `700`.
`parse_amount("12.50")` is `1250`, `parse_amount("-4.00")` is `-400`, `parse_amount("$1,234.56")` is `123456`, and `parse_amount("($1,234.56)")` is `-123456`.

Acceptance: the examples above pass, invalid tokens raise `ValueError`, and both modules agree on the sign.
