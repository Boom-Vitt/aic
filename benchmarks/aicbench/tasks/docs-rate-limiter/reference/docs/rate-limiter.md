# Token bucket

`TokenBucket` is constructed with `capacity`, `refill_per_second`, and `now`.

`acquire` returns True when the requested tokens are taken.
`acquire` returns False when the bucket does not hold enough tokens.
default amount is 1

Stored tokens never exceed capacity.
