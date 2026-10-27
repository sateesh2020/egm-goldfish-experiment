"""In-process link storage."""
from typing import Dict, Optional

MAX_SLUG_LEN = 16


class LinkStore:
    def __init__(self) -> None:
        self._links: Dict[str, str] = {}

    def put(self, slug: str, url: str) -> None:
        if len(slug) > MAX_SLUG_LEN:
            raise ValueError("slug too long")
        self._links[slug] = url

    def get(self, slug: str) -> Optional[str]:
        return self._links.get(slug)
