def total_attempts(max_retries: int) -> int:
    if type(max_retries) is not int or max_retries < 0:
        raise ValueError("max_retries")
    return max_retries + 1
