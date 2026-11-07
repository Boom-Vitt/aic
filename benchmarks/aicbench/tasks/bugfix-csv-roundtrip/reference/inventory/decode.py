def _parse(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    row: list[str] = []
    field: list[str] = []
    quoted = False
    index = 0
    while index < len(text):
        character = text[index]
        if quoted:
            if character == '"':
                if index + 1 < len(text) and text[index + 1] == '"':
                    field.append('"')
                    index += 2
                    continue
                quoted = False
                index += 1
                continue
            field.append(character)
            index += 1
            continue
        if character == '"':
            if field:
                raise ValueError("csv")
            quoted = True
            index += 1
            continue
        if character == ",":
            row.append("".join(field))
            field = []
            index += 1
            continue
        if character == "\n":
            row.append("".join(field))
            rows.append(row)
            row = []
            field = []
            index += 1
            continue
        field.append(character)
        index += 1
    if quoted or field or row:
        raise ValueError("csv")
    return rows


def decode_rows(text, columns):
    if not isinstance(text, str) or not text.endswith("\n") or not isinstance(columns, list):
        raise ValueError("csv")
    rows = _parse(text)
    if not rows or rows[0] != list(columns):
        raise ValueError("header")
    decoded = []
    for row in rows[1:]:
        if len(row) != len(columns):
            raise ValueError("row")
        decoded.append(dict(zip(columns, row)))
    return decoded
