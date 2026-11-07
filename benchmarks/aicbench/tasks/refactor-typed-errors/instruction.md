`loader.load(data, schema)` copies the schema keys from `data`. `schema` maps a key to `int` or `str`. A missing key currently raises `ValueError`. A present value of the wrong type also raises `ValueError`. Success values stay the same.

Introduce `errors.ConfigError`, `errors.MissingKey`, and `errors.BadType`. The two specific classes subclass `ConfigError`, and `ConfigError` subclasses `Exception`. Raise `MissingKey` when a schema key is absent. Raise `BadType` when the value's type is not the schema type. Do not accept booleans as integers. Leave successful output unchanged: `load({"port": 80, "name": "api", "extra": 1}, {"port": int, "name": str})` returns `{"port": 80, "name": "api"}`.

Acceptance: callers can catch the specific classes, and successful loads still return only the schema keys.
