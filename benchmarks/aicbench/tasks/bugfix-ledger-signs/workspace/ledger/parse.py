def parse_amount(token: str) -> int:
    text = token.strip()
    negative = text.startswith("-")
    text = text.strip("()").lstrip("-").lstrip("$").replace(",", "")
    if text.count(".") != 1:
        raise ValueError(token)
    whole, frac = text.split(".")
    if not whole.isdigit() or len(frac) != 2 or not frac.isdigit():
        raise ValueError(token)
    cents = int(whole) * 100 + int(frac)
    return -cents if negative else cents
