from validation import require_email


def normalize_user(email: str) -> str:
    return require_email(email)
