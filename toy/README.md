# shortener
A tiny link shortener. `shortener/api.py` exposes `create_link` and `resolve`; the web layer (not in this repo) runs them under 4 gunicorn worker processes.
