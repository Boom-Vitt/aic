def _check(merchandise_cents, shipping_cents):
    if type(merchandise_cents) is not int or type(shipping_cents) is not int or merchandise_cents < 0 or shipping_cents < 0:
        raise ValueError("money")


def _percent(percent):
    def apply(merchandise_cents, shipping_cents):
        _check(merchandise_cents, shipping_cents)
        discount = (merchandise_cents * percent + 50) // 100
        return merchandise_cents - discount, shipping_cents
    return apply


def _free_ship(merchandise_cents, shipping_cents):
    _check(merchandise_cents, shipping_cents)
    return merchandise_cents, 0


REGISTRY = {
    "SAVE10": _percent(10),
    "SAVE20": _percent(20),
    "FREESHIP": _free_ship,
}
