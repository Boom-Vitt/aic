def normalize_user(email: str) -> str:
    text = email.strip().lower()
    if "@" not in text:
        raise ValueError(email)
    return text
