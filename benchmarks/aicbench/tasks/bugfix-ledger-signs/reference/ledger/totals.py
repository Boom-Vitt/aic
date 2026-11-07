from .parse import parse_amount


def net_cents(lines: list[str]) -> int:
    total = 0
    for line in lines:
        if not isinstance(line, str):
            raise ValueError("lines must be strings")
        if line.strip() == "":
            continue
        total += parse_amount(line)
    return total
