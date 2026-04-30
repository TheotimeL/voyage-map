"""URL-safe slug generation. Base58 (no 0/O/I/l) keeps slugs unambiguous."""

import secrets

ALPHABET = "123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"


def make_slug(length: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
