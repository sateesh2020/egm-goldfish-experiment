"""HTTP-agnostic handlers used by the web layer."""
from .slugs import make_slug
from .store import LinkStore

store = LinkStore()


def create_link(url: str) -> str:
    slug = make_slug(url)
    store.put(slug, url)
    return slug


def resolve(slug: str):
    """Return (status, location) for a redirect."""
    url = store.get(slug)
    if url is None:
        return 404, None
    return 302, url
