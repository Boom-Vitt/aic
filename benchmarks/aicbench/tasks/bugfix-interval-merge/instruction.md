Meetings are half-open integer intervals `[start, end)`. `end` must be greater than `start`. Both ends are `int` values, not booleans. `schedule.intervals.overlaps(a, b)` is true only when the intervals share a point. Touching endpoints do not overlap: `[1, 2)` and `[2, 3)` is false. `[1, 3)` and `[2, 4)` is true. An invalid interval raises `ValueError`.

`schedule.agenda.merge_busy(meetings)` returns the merged busy ranges. Sort by start, then end. Merge only overlapping intervals. Leave touching intervals separate. Keep every meeting, including the last one and a list of one. An empty list returns `[]`.
`merge_busy([(5, 7), (1, 3), (2, 4)])` is `[(1, 4), (5, 7)]`.
`merge_busy([(1, 2), (2, 3)])` is `[(1, 2), (2, 3)]`.
`merge_busy([(1, 4)])` is `[(1, 4)]`.

Acceptance: overlap uses a strict half-open test, and merging preserves touching meetings and the final meeting.
