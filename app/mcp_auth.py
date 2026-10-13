"""Authentication boundary shared by the citizen and officer MCP servers.
Only the portal's OAuth authorization server may establish the caller's identity.
Never accept a mobile number, username, role, or application owner from a tool
argument as proof of identity. This module verifies signed JWTs before tools run.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Literal
import re
import time

import jwt


Role = Literal["citizen", "officer"]
ProgramCheck = Callable[[str, str, str], bool]


@dataclass(frozen=True)
class Identity:
    """Identity derived exclusively from a verified portal-issued access token."""

    subject: str
    role: Role
    client_id: str
    expires_at: int
    token_kind: str
    jti: str
    mobile: str | None = None
    officer_username: str | None = None


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    # Reuse keys across requests; PyJWKClient refreshes if a key ID is unknown.
    return jwt.PyJWKClient(url, cache_keys=True)


def verify_mcp_token(
    token: str,
    *,
    issuer: str,
    resource: str,
    expected_role: Role,
    jwks_url: str,
    program_is_active: ProgramCheck | None = None,
    jwks_client: jwt.PyJWKClient | None = None,
) -> Identity | None:
    """Verify OAuth JWT signature, resource binding, permission and subject.

    Returns None on unauthorized access, for the HTTP layer to return 401.
    A program token additionally requires a database revocation/status check;
    it fails closed if no such checker is supplied.

    `resource` must equal the exact public MCP URL used as the OAuth audience,
    e.g. https://example.in/mcp/citizen (not the portal's base URL).
    """
    if not token or expected_role not in ("citizen", "officer"):
        return None

    try:
        client = jwks_client or _jwks_client(jwks_url)
        public_key = client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=resource,
            issuer=issuer,
            options={"require": ["iss", "sub", "aud", "exp", "iat", "jti"]},
            leeway=10,
        )
    except (jwt.PyJWTError, ValueError, TypeError, OSError):
        return None

    # Never allow the same token to authorize a different server/role.
    if claims.get("aud") != resource:
        return None
    if claims.get("role") != expected_role:
        return None
    if claims.get("scope") != expected_role:
        return None

    subject = claims.get("sub")
    client_id = claims.get("client_id")
    jti = claims.get("jti")
    kind = claims.get("kind")
    expires_at = claims.get("exp")
    if not isinstance(subject, str) or not isinstance(client_id, str) or not client_id:
        return None
    if not isinstance(jti, str) or not jti or type(expires_at) is not int:
        return None
    if kind not in ("access", "program"):
        return None

    if kind == "access":
        # A session cannot be renewed forever by refreshing its access token.
        session_ends = claims.get("session_ends")
        if type(session_ends) is not int or time.time() >= session_ends:
            return None
    else:
        # Only officers can use administrator-issued program tokens. Their JTI
        # must still exist and remain unrevoked in oauth_program_tokens.
        if expected_role != "officer" or program_is_active is None:
            return None
        try:
            if not program_is_active(jti, subject, resource):
                return None
        except Exception:
            return None  # Database unavailable: deny rather than fail open.

    if expected_role == "citizen":
        if not re.fullmatch(r"citizen:[0-9]{10}", subject):
            return None
        return Identity(subject, "citizen", client_id, expires_at, kind, jti,
                        mobile=subject.split(":", 1)[1])

    if not re.fullmatch(r"officer:[A-Za-z0-9_.@-]{1,64}", subject):
        return None
    return Identity(subject, "officer", client_id, expires_at, kind, jti,
                    officer_username=subject.split(":", 1)[1])
