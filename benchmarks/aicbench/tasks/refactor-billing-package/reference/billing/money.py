def line_total(unit_cents, qty):
    if type(unit_cents) is not int or type(qty) is not int or unit_cents < 0 or qty < 0:
        raise ValueError("line")
    return unit_cents * qty
