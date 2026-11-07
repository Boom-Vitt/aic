Write `docs/cli.md` from `cli.py`. Do not change any Python file.

Document every subcommand registered on the parser returned by `build_parser`, and include each help string passed to `add_argument` exactly as argparse stores it. The subcommand names and those help strings must appear as literal text. Do not invent flags that the parser does not define, and you do not need to repeat the automatic `-h` text.

Acceptance: a reader can find every subcommand and every stored help string in the document, and the Python bytes are unchanged.
