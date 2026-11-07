def slugify(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("value")
    parts: list[str] = []
    current: list[str] = []
    for character in value.casefold():
        if character.isalnum():
            current.append(character)
        elif current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    if not parts:
        raise ValueError("slug")
    return "-".join(parts)
