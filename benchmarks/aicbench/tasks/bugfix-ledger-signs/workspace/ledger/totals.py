from .parse import parse_amount


def net_cents(lines: list[str]) -> int:
    total = 0
    for line in lines:
        if line.strip() == "":
            continue
        total += abs(parse_amount(line))
    return total
