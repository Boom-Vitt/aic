def format_hhmmss(seconds: int) -> str:
    if type(seconds) is not int or seconds < 0:
        raise ValueError("seconds")
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
