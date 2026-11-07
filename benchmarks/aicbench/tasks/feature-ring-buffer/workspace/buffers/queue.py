class Queue:
    def __init__(self):
        self._items = []

    def put(self, item):
        self._items.append(item)

    def get(self):
        if not self._items:
            raise IndexError("empty")
        return self._items.pop(0)
