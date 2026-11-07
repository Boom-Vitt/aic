TRANSITIONS = {
    "draft": ("review",),
    "review": ("draft", "approved", "rejected"),
    "approved": ("archived",),
    "rejected": ("draft",),
    "archived": (),
}


def destinations(state):
    if state not in TRANSITIONS:
        raise KeyError(state)
    return TRANSITIONS[state]
