import re

_DURATION = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")


def parse_duration(text: str) -> int:
    if not isinstance(text, str) or text == "":
        raise ValueError("duration")
    match = _DURATION.fullmatch(text)
    if match is None or all(group is None for group in match.groups()):
        raise ValueError("duration")
    for group in match.groups():
        if group is not None and len(group) > 1 and group.startswith("0"):
            raise ValueError("duration")
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds
