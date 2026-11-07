def is_within(root: str, candidate: str) -> bool:
    if not isinstance(root, str) or not isinstance(candidate, str):
        return False
    return candidate.startswith(root)
