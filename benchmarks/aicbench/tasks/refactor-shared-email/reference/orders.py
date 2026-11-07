from validation import require_email


def normalize_contact(email: str) -> str:
    return require_email(email)
