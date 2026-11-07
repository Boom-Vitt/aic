def _field(value) -> str:
    if not isinstance(value, str):
        raise ValueError("field")
    if any(character in value for character in ",\"\n"):
        return '"' + value.replace('"', '""') + '"'
    return value


def encode_rows(columns, rows) -> str:
    if not isinstance(columns, list) or not columns or any(not isinstance(column, str) or column == "" for column in columns):
        raise ValueError("columns")
    lines = [",".join(_field(column) for column in columns)]
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(columns):
            raise ValueError("row")
        lines.append(",".join(_field(row[column]) for column in columns))
    return "\n".join(lines) + "\n"
