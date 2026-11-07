Write `docs/api.md` from `stats/__init__.py`. Do not change any Python file.

For every public function defined in that module, add a heading `## name` and a line `signature: name(param, param)` listing the parameter names in order, excluding `self`. Do not document functions whose names start with an underscore. Do not add headings for functions that are not defined there.

Acceptance: the headings and signature lines match the source, and the Python bytes are unchanged.
