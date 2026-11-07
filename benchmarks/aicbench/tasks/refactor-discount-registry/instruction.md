Move discount codes out of the `if` chain in `checkout.py`. Put them in `discounts.REGISTRY`, a dictionary whose keys are `SAVE10`, `SAVE20`, and `FREESHIP`. Each value is a function of `(merchandise_cents, shipping_cents)` and returns a tuple of the same two integers.

`checkout.price(merchandise_cents, shipping_cents, code)` checks that both amounts are `int` values of at least 0. `code` None or `""` returns the amounts unchanged. Any other string looks up `REGISTRY` and returns that function's result. An unknown code raises `KeyError`.
Percent codes use half-up integer arithmetic. The discount is `(merchandise_cents * percent + 50) // 100`, subtracted from merchandise, and shipping stays unchanged. `SAVE10` is 10 percent and `SAVE20` is 20 percent. `FREESHIP` leaves merchandise unchanged and sets shipping to 0.
`price(105, 20, "SAVE10")` is `(94, 20)`. `price(100, 25, "FREESHIP")` is `(100, 0)`. `price(100, 25, None)` is `(100, 25)`.

`checkout.py` must use `REGISTRY` and must not hard-code the three code strings. Behavior stays on `checkout.price`.

Acceptance: the registry owns the codes, and the numeric examples pass.
