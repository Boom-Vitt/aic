def format_event(name, detail) -> str:
    if not isinstance(name, str) or not isinstance(detail, str):
        raise TypeError("event")
    return f"{name}: {detail}"
