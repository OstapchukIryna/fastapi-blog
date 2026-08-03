"""Settings and cryptography — the bottom layer, which imports nothing of ours.

Nothing here knows about HTTP, the database or the domain. That is what
makes it safe for every other layer to depend on.
"""
