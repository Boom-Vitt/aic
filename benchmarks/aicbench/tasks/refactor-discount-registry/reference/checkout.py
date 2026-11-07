from discounts import REGISTRY


def price(merchandise_cents, shipping_cents, code):
    if type(merchandise_cents) is not int or type(shipping_cents) is not int or merchandise_cents < 0 or shipping_cents < 0:
        raise ValueError("money")
    if code is None or code == "":
        return merchandise_cents, shipping_cents
    if not isinstance(code, str):
        raise TypeError("code")
    return REGISTRY[code](merchandise_cents, shipping_cents)
