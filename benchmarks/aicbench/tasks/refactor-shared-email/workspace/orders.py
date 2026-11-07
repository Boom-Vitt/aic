def normalize_contact(email: str) -> str:
    text = email.strip()
    if "@" not in text or "." not in text.split("@", 1)[-1]:
        raise ValueError(email)
    return text
