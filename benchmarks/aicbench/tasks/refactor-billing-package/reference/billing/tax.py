def tax_cents(amount, rate_bps):
    if type(amount) is not int or type(rate_bps) is not int or amount < 0 or not 0 <= rate_bps <= 10000:
        raise ValueError("tax")
    return (amount * rate_bps + 5000) // 10000
