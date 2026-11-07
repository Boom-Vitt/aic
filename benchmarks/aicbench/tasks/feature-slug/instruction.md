Add `textkit.slug.slugify(value)`. Keep `textkit.case.title_case` working: `title_case("hello world")` stays `"Hello World"`.

`slugify` accepts a string and casefolds it. Every run of characters that are not Unicode letters or digits becomes one hyphen. Underscores are separators. Strip hyphens from both ends. `"Hello, World!"` becomes `"hello-world"`. `"Äpfel & Birnen"` becomes `"äpfel-birnen"`. `"A--B"` becomes `"a-b"`. `"Version 2"` becomes `"version-2"`. An empty result, including `"---"`, raises `ValueError`. A non-string raises `TypeError`.

Add `tests/__init__.py` and `tests/test_slug.py`. The new tests must be a `unittest.TestCase`, must assert the `hello-world` result, and must pass under `python -m unittest tests.test_slug` from the workspace.

Acceptance: the slug examples pass, title case is unchanged, and the new unit tests pass.
