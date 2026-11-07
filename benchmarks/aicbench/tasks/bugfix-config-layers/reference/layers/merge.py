import copy


def merge(base, overlay):
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        raise TypeError("layers must be dictionaries")
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result
