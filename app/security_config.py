"""Secure portal settings, independent of Flask for offline tests."""

import os
from urllib.parse import urlsplit

_INSECURE = {"ssp-prod-key-2023-donotshare", "change-me-before-deploying", "secret", "changeme"}
_LOCAL = {"localhost", "127.0.0.1", "::1"}


def require_flask_secret(environ=None):
    env = os.environ if environ is None else environ
    value = env.get("SECRET_KEY", "")
    if not isinstance(value, str) or len(value.encode("utf-8")) < 32 or value.strip().lower() in _INSECURE:
        raise RuntimeError("Set SECRET_KEY to a persistent cryptographically random value of at least 32 bytes")
    return value


def configure_session_security(app, public_base_url):
    try:
        p = urlsplit(public_base_url)
        host = p.hostname
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid PUBLIC_BASE_URL") from exc
    if (p.scheme not in {"http", "https"} or not host or p.username or p.password
            or p.query or p.fragment):
        raise RuntimeError("PUBLIC_BASE_URL must be an http(s) origin without credentials or query")
    if p.scheme != "https" and host not in _LOCAL:
        raise RuntimeError("Use HTTPS for PUBLIC_BASE_URL outside localhost")
    app.config.update(
        SESSION_COOKIE_SECURE=p.scheme == "https",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="sewasetu_session",
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
    )
