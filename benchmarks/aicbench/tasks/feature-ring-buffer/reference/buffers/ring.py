class RingBuffer:
    def __init__(self, capacity: int):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity")
        self._capacity = capacity
        self._items = []

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._items)

    def append(self, item) -> None:
        if len(self._items) == self._capacity:
            self._items.pop(0)
        self._items.append(item)

    def pop(self):
        if not self._items:
            raise IndexError("empty")
        return self._items.pop(0)

    def to_list(self):
        return list(self._items)
