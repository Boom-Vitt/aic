from .money import line_total
from .tax import tax_cents


def total(lines, shipping_cents, rate_bps):
    if type(shipping_cents) is not int or shipping_cents < 0:
        raise ValueError("shipping")
    goods = 0
    for line in lines:
        goods += line_total(line["unit_cents"], line["qty"])
    return goods + tax_cents(goods, rate_bps) + shipping_cents
