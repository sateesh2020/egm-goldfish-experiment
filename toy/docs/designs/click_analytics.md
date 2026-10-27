# Click Analytics for Short Links

* **Author:** example
* **Status:** Draft

## Objective

Product wants to show link owners how many times each short link was clicked.

## Background

Short links are created by `create_link` and resolved by `resolve` in
`shortener/api.py`. Slugs are generated with MD5 in `shortener/slugs.py`, and
links are read with `LinkStore.get_url(slug)` in `shortener/store.py`.

## Design

When `resolve` succeeds, it increments the click count for the slug before it
returns the redirect. Counts live in the analytics database (Postgres, hosted
by the data team). The increment reads the current count and writes back
`count + 1`.

Each click event is also forwarded to the CEP so downstream teams can use it.

Phase 1 also adds a pluggable, ML-based bot-detection framework, so that we can
filter bot clicks in the future.

## Detailed Implementation Plan

1. Add a counter module.
2. Update the API.
3. Add the bot-detection plugin interface.
4. Ship it.
