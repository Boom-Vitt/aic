"""Offline scoring for routing packs.

The default pack is the dev fixture. The release pack is heldout-v2.
The scorer compares a decision file with the selected pack's labels. It does not
classify request text and it does not call a model.
"""
