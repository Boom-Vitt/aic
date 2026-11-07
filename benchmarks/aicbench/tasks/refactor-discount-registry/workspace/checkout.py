def price(merchandise_cents, shipping_cents, code):
    if type(merchandise_cents) is not int or type(shipping_cents) is not int or merchandise_cents < 0 or shipping_cents < 0:
        raise ValueError("money")
    if code is None or code == "":
        return merchandise_cents, shipping_cents
    if code == "SAVE10":
        discount = (merchandise_cents * 10 + 50) // 100
        return merchandise_cents - discount, shipping_cents
    if code == "SAVE20":
        discount = (merchandise_cents * 20 + 50) // 100
        return merchandise_cents - discount, shipping_cents
    if code == "FREESHIP":
        return merchandise_cents, 0
    raise KeyError(code)
