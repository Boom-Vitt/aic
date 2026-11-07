from .merge import merge


def load_config(defaults, user):
    return merge(defaults, user)
