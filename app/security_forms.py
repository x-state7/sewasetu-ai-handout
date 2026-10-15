"""Session-backed CSRF tokens for all browser form POST endpoints.

Machine endpoints (/oauth/token, /oauth/register, /oauth/revoke) deliberately
remain exempt: they authenticate using OAuth credentials rather than cookies.
"""

import secrets
from flask import abort, request, session

_EXEMPT_API_PATHS = frozenset({"/oauth/token", "/oauth/register", "/oauth/revoke"})


def init_csrf(app):
    @app.context_processor
    def csrf_for_templates():
        return {"csrf_token": csrf_token}

    @app.before_request
    def check_browser_csrf():
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path not in _EXEMPT_API_PATHS:
            expected = session.get("_csrf_token", "")
            supplied = request.form.get("_csrf_token", "") or request.headers.get("X-CSRF-Token", "")
            if not expected or not supplied or not secrets.compare_digest(expected, supplied):
                abort(400, description="Form expired or invalid. Refresh the page and try again.")


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token
