Refactor `billing.py` into a package without changing behavior. Remove `billing.py`. Create `billing/money.py`, `billing/tax.py`, `billing/invoice.py`, and `billing/__init__.py`.

Move `line_total(unit_cents, qty)` into `money.py`. Both arguments are `int` values of at least 0, otherwise `ValueError`. The result is their product.
Move `tax_cents(amount, rate_bps)` into `tax.py`. `amount` is an `int` of at least 0 and `rate_bps` is an `int` from 0 through 10000. Tax uses half-up integer arithmetic: `(amount * rate_bps + 5000) // 10000`.
Move `total(lines, shipping_cents, rate_bps)` into `invoice.py`. Each line has `unit_cents` and `qty`. Goods are the sum of line totals. Tax applies to goods only. Shipping is an `int` of at least 0 and is not taxed. The total is goods + tax + shipping.
`billing/__init__.py` re-exports `line_total`, `tax_cents`, and `total`.

`total([{"unit_cents": 250, "qty": 2}], 50, 1000)` is `600`: goods 500, tax 50, shipping 50.
`tax_cents(10, 750)` is `1`.

Acceptance: the package layout replaces `billing.py` and the numeric results stay the same.
