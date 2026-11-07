class TokenBucket:
    """In-memory token bucket driven by an injected clock."""

    def __init__(self, capacity, refill_per_second, now):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("capacity")
        if type(refill_per_second) is not int or refill_per_second < 0:
            raise ValueError("refill")
        if not callable(now):
            raise TypeError("now")
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._now = now
        self._tokens = capacity
        self._updated = now()

    def _refill(self) -> None:
        current = self._now()
        elapsed = current - self._updated
        if elapsed < 0:
            raise ValueError("clock")
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_second)
        self._updated = current

    def acquire(self, amount=1) -> bool:
        if type(amount) is not int or amount <= 0:
            raise ValueError("amount")
        self._refill()
        if self._tokens < amount:
            return False
        self._tokens -= amount
        return True
