`users.normalize_user` and `orders.normalize_contact` each validate email differently. Extract one helper, `validation.require_email`, and call it from both functions.

The helper strips surrounding whitespace and casefolds the text. The result must contain exactly one `@`, a nonempty local part, and a domain that contains a dot. The domain cannot start or end with a dot. The text cannot contain whitespace after stripping. On success return the normalized string. Otherwise raise `ValueError`.
`normalize_user("  User@Example.com  ")` and `normalize_contact("  User@Example.com  ")` both return `user@example.com`.
`admin@localhost`, `a@b@c.com`, and `@example.com` raise `ValueError`.

Acceptance: both public functions call `validation.require_email`, and they return the same normalized address.
