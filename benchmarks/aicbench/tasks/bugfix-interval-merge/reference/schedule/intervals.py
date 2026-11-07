def pair(interval):
    if not isinstance(interval, tuple) or len(interval) != 2:
        raise ValueError("interval")
    start, end = interval
    if type(start) is not int or type(end) is not int or end <= start:
        raise ValueError("interval")
    return start, end


def overlaps(left, right) -> bool:
    a0, a1 = pair(left)
    b0, b1 = pair(right)
    return a0 < b1 and b0 < a1
