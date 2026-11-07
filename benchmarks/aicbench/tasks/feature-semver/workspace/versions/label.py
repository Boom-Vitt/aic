def display_label(text: str) -> str:
    if not isinstance(text, str) or text == "":
        raise ValueError("label")
    return f"v{text}"
