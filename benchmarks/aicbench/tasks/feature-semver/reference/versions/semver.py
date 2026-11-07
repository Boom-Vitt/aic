def parse_version(text: str) -> tuple[int, int, int]:
    if not isinstance(text, str):
        raise ValueError("version")
    parts = text.split(".")
    if len(parts) != 3:
        raise ValueError("version")
    numbers = []
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part.startswith("0")):
            raise ValueError("version")
        numbers.append(int(part))
    return numbers[0], numbers[1], numbers[2]


def compare_versions(left: str, right: str) -> int:
    parsed_left = parse_version(left)
    parsed_right = parse_version(right)
    if parsed_left < parsed_right:
        return -1
    if parsed_left > parsed_right:
        return 1
    return 0


def higher(left: str, right: str) -> str:
    return right if compare_versions(left, right) < 0 else left
