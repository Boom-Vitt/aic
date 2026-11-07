def mean(values):
    """Return the arithmetic mean of a nonempty sequence of numbers."""
    if not values:
        raise ValueError("values")
    return sum(values) / len(values)


def median(values):
    """Return the median of a nonempty sequence of numbers."""
    if not values:
        raise ValueError("values")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def clamp(value, low, high):
    """Return value limited to the inclusive range from low to high."""
    if low > high:
        raise ValueError("range")
    return min(max(value, low), high)
