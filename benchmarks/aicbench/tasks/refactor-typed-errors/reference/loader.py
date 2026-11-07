from errors import BadType, MissingKey


def load(data, schema):
    if not isinstance(data, dict) or not isinstance(schema, dict):
        raise ValueError("config")
    result = {}
    for key, kind in schema.items():
        if kind not in (int, str):
            raise ValueError("schema")
        if key not in data:
            raise MissingKey(key)
        value = data[key]
        if type(value) is not kind:
            raise BadType(key)
        result[key] = value
    return result
