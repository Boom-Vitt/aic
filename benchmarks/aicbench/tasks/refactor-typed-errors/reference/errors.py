class ConfigError(Exception):
    pass


class MissingKey(ConfigError):
    pass


class BadType(ConfigError):
    pass
