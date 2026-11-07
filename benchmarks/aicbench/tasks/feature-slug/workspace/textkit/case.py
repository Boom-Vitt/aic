def title_case(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("value")
    return " ".join(word.capitalize() for word in value.split(" "))
