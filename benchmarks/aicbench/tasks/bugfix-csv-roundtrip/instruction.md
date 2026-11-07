Fix the inventory CSV codec. `inventory.encode.encode_rows(columns, rows)` returns UTF-8 text using `\n` line endings and a trailing newline. The first line is the header and must equal `columns`, which is a nonempty list of nonempty strings. Each row is a dictionary whose keys are exactly those columns. Quote a field that contains a comma, a double quote, or a newline, and escape a quote by doubling it.

`inventory.decode.decode_rows(text, columns)` reverses that text. A header mismatch, a ragged row, or an unclosed quote raises `ValueError`. A file with only the header returns `[]`.

Acceptance: a row whose fields contain a comma, a quote, and a newline round-trips, and a wrong header raises `ValueError`.
