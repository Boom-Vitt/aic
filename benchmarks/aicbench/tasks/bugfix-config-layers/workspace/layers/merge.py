import copy


def merge(base, overlay):
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        raise TypeError("layers must be dictionaries")
    result = copy.deepcopy(base)
    result.update(copy.deepcopy(overlay))
    return result
