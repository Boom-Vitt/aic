def encode_rows(columns, rows) -> str:
    if not isinstance(columns, list) or not columns:
        raise ValueError("columns")
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(row[column]) for column in columns))
    return "\n".join(lines) + "\n"
