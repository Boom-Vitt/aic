Add `buffers.ring.RingBuffer`. Leave `buffers.queue.Queue` as a FIFO: `put` then `get` returns the oldest item, and `get` on an empty queue raises `IndexError`.

`RingBuffer(capacity)` requires `capacity` to be an `int` of at least 1. Otherwise raise `ValueError`. `append(item)` adds an item. When the buffer is full, the oldest item is dropped. `pop()` removes and returns the oldest item, or raises `IndexError` when empty. `__len__` is the current size. `capacity` is the configured limit. `to_list()` returns items from oldest to newest and does not mutate the buffer.

For capacity 2, appending `a`, `b`, then `c` leaves `[b, c]`. The next `pop()` returns `b`.

Add `tests/__init__.py` and `tests/test_ring.py` as a unittest module that mentions `append` and `pop` and passes under `python -m unittest tests.test_ring`.

Acceptance: overwrite order, empty pop, capacity rejection, and the existing queue still match this contract.
