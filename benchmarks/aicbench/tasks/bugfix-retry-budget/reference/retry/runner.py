from .policy import total_attempts


def run(operation, *, max_retries, retryable, sleep):
    if not isinstance(retryable, tuple) or not all(isinstance(item, type) and issubclass(item, BaseException) for item in retryable):
        raise TypeError("retryable")
    attempts = total_attempts(max_retries)
    for index in range(attempts):
        try:
            return operation()
        except retryable:
            if index == attempts - 1:
                raise
            sleep(index + 1)
