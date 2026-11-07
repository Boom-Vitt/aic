Add cursor pagination in `pages.cursor`. Keep `pages.window.window([1, 2, 3, 4], 2, 2)` equal to `[3, 4]`.

`encode_cursor(offset)` accepts an `int` of at least 0 and returns the URL-safe base64 text of its decimal ASCII form, without trailing `=` padding. A negative offset raises `ValueError`. A value that is not an `int`, including `True`, raises `TypeError`. `decode_cursor(token)` reverses a canonical unpadded token. Reject tokens that are empty, contain `=`, contain whitespace, or are not a canonical decimal integer. Leading zeros are rejected except for offset 0. A bad token raises `ValueError`.

`page(items, *, limit, cursor=None)` returns `{"items": [...], "next_cursor": ...}`. `items` is a list and is not mutated. `limit` is an `int` from 1 to 100 inclusive. `cursor=None` starts at offset 0. Otherwise the cursor is decoded. `next_cursor` is `None` when the page reaches the end, otherwise the cursor of the next offset.
`page([0, 1, 2, 3, 4], limit=2)` returns items `[0, 1]` and a cursor that decodes to 2. The following page returns `[2, 3]` and a cursor that decodes to 4. The last page returns `[4]` and `next_cursor` None. An offset past the end returns empty items and `next_cursor` None.

Add `tests/__init__.py` and `tests/test_cursor.py` mentioning `next_cursor`, runnable as `python -m unittest tests.test_cursor`.

Acceptance: cursors round-trip, limits are bounded, and the older window helper is unchanged.
