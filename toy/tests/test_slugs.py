from shortener.slugs import make_slug


def test_deterministic():
    assert make_slug("https://example.com") == make_slug("https://example.com")


def test_length():
    assert len(make_slug("https://example.com", length=5)) == 5
