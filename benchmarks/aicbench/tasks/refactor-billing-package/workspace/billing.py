def line_total(unit_cents, qty):
    if type(unit_cents) is not int or type(qty) is not int or unit_cents < 0 or qty < 0:
        raise ValueError("line")
    return unit_cents * qty


def tax_cents(amount, rate_bps):
    if type(amount) is not int or type(rate_bps) is not int or amount < 0 or not 0 <= rate_bps <= 10000:
        raise ValueError("tax")
    return (amount * rate_bps + 5000) // 10000


def total(lines, shipping_cents, rate_bps):
    if type(shipping_cents) is not int or shipping_cents < 0:
        raise ValueError("shipping")
    goods = 0
    for line in lines:
        goods += line_total(line["unit_cents"], line["qty"])
    return goods + tax_cents(goods, rate_bps) + shipping_cents
