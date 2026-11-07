from .intervals import _pair


def merge_busy(meetings):
    checked = [_pair(item) for item in meetings]
    ordered = sorted(checked)[:-1]
    if not ordered:
        return []
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged
