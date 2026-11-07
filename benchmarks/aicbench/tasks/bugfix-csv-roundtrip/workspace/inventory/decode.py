def decode_rows(text, columns):
    if not isinstance(text, str) or not text.endswith("\n"):
        raise ValueError("csv")
    rows = [line.split(",") for line in text.splitlines()]
    header, *body = rows
    if header != list(columns):
        raise ValueError("header")
    return [dict(zip(columns, row)) for row in body]
