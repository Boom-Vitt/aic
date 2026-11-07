def load(data, schema):
    if not isinstance(data, dict) or not isinstance(schema, dict):
        raise ValueError("config")
    result = {}
    for key, kind in schema.items():
        if key not in data:
            raise ValueError(f"missing {key}")
        value = data[key]
        if kind not in (int, str) or type(value) is not kind:
            raise ValueError(f"bad type {key}")
        result[key] = value
    return result
