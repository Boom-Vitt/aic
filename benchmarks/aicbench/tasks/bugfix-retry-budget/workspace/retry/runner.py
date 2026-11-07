from .policy import total_attempts


def run(operation, *, max_retries, retryable, sleep):
    attempts = total_attempts(max_retries)
    error = None
    for index in range(attempts):
        try:
            return operation()
        except Exception as exc:
            error = exc
            if index >= attempts - 1:
                raise
            sleep(index + 1)
    raise error
