import unittest

from buffers.ring import RingBuffer


class RingTests(unittest.TestCase):
    def test_append_drops_the_oldest_item(self):
        ring = RingBuffer(2)
        ring.append("a")
        ring.append("b")
        ring.append("c")
        self.assertEqual(ring.to_list(), ["b", "c"])
        self.assertEqual(ring.pop(), "b")


if __name__ == "__main__":
    unittest.main()
