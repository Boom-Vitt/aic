Fix layered configuration. `layers.merge.merge(base, overlay)` returns a new dictionary. Later values win. When both sides have a dictionary for the same key, merge those dictionaries recursively. Lists and other scalars from the overlay replace the base value. `None` in the overlay replaces the base value. Do not mutate either argument.

`layers.load.load_config(defaults, user)` returns `merge(defaults, user)`. User values win, including nested keys that the user does not mention, which stay at the default.

Acceptance: nested dictionaries merge, lists are replaced, neither input is mutated, and a user value beats a default.
