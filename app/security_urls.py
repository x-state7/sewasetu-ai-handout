"""Default-deny remote OAuth client metadata URL fetching.

Dynamic Client Registration stays usable by all compatible clients. URL-based
Client ID Metadata Documents require an explicit, trusted hostname allowlist.
"""

import ipaddress
import os
from urllib.parse import urlsplit


def allowed_client_metadata_url(value, environ=None):
    env = os.environ if environ is None else environ
    allow = {h.strip().lower() for h in env.get("OAUTH_CIMD_ALLOWED_HOSTS", "").split(",") if h.strip()}
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        if not allow or not host or host not in allow or parts.scheme != "https":
            return False
        if parts.username or parts.password or parts.fragment or parts.port not in (None, 443):
            return False
        if len(value) > 512:
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        if host == "localhost" or host.endswith(".localhost"):
            return False
        return True
    except (TypeError, ValueError):
        return False
