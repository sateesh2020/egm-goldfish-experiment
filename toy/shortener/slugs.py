"""Slug generation for short links."""
import hashlib
import string

ALPHABET = string.digits + string.ascii_letters  # base62


def make_slug(url: str, length: int = 7) -> str:
    """Return a deterministic base62 slug derived from the SHA-256 of the URL."""
    digest = int(hashlib.sha256(url.encode("utf-8")).hexdigest(), 16)
    chars = []
    while digest and len(chars) < length:
        digest, rem = divmod(digest, 62)
        chars.append(ALPHABET[rem])
    return "".join(chars)
