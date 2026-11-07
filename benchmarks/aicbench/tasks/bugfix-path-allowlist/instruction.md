Fix lexical path checks. Do not touch the filesystem. Paths are POSIX strings.

`safepath.policy.is_within(root, candidate)` is true when both values are absolute and `candidate` is `root` or a descendant. Compare path components, not string prefixes. `/srv/app` contains `/srv/app/data` and does not contain `/srv/app-secret` or `/srv/application`. A relative candidate is false. `.` and `..` are resolved lexically before the comparison.

`safepath.join.join_under(root, child)` joins a relative child under an absolute root and returns an absolute POSIX path. An absolute child, an empty child, or a child that resolves outside the root raises `ValueError`. `join_under("/srv/app", "data/file.txt")` is `/srv/app/data/file.txt`. `join_under("/srv/app", "sub/../data")` is `/srv/app/data`. `join_under("/srv/app", "/etc/passwd")` and `join_under("/srv/app", "../secret")` raise `ValueError`.

Acceptance: prefix tricks and absolute children cannot leave the root.
