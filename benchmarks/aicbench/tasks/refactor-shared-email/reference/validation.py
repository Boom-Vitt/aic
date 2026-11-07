def require_email(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("email")
    text = value.strip().casefold()
    if text.count("@") != 1 or any(character.isspace() for character in text):
        raise ValueError("email")
    local, domain = text.split("@")
    if not local or domain.startswith(".") or domain.endswith(".") or "." not in domain:
        raise ValueError("email")
    return text
