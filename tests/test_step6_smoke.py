
"""Step 6 static production configuration tests."""

import os
from pathlib import Path
from urllib.parse import urlsplit


def test_public_base_url_uses_https():
    url = os.environ.get(
        "PUBLIC_BASE_URL", "https://example.invalid"
    )
    assert urlsplit(url).scheme == "https"


def test_secret_length():
    secret = os.environ.get(
        "SECRET_KEY", "a" * 32
    )
    assert len(secret.encode("utf-8")) >= 32


def test_required_files_exist():
    root = Path(__file__).resolve().parent.parent

    files = [
        "app/app.py",
        "app/mcp_auth.py",
        "app/mcp_citizen.py",
        "app/mcp_officer.py",
        "deploy/Caddyfile",
        "deploy/preflight.py",
    ]

    for filename in files:
        assert (root / filename).exists(), filename
