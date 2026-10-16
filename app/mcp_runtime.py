
"""OAuth-backed MCP resource servers using MCP SDK v2."""

# this new version retains the original JWT verifier, 
# adds the authenticated subject to the SDK token context, and 
# configures the hostname security checks for your public deployment.

#the MCP SDK's HTTP transport can reject requests from non-localhost hosts
#by default. Explicitly configuring allowed_hosts is required for deployment 
# behind your real domain
import os
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl
from mcp.server import MCPServer

from mcp.server.auth.provider import (
    AccessToken,
    TokenVerifier,
)
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import (
    get_access_token,
)
from mcp.server.transport_security import (
    TransportSecuritySettings,
)

from mcp_auth import verify_mcp_token


def required(name):
    value = os.environ.get(name, "").strip()

    if not value:
        raise RuntimeError(
            "Missing environment variable: " + name
        )

    return value


class PortalTokenVerifier(TokenVerifier):
    def __init__(
        self,
        role,
        resource,
        issuer,
        jwks_url,
    ):
        self.role = role
        self.resource = resource
        self.issuer = issuer
        self.jwks_url = jwks_url

    async def verify_token(self, raw):
        identity = verify_mcp_token(
            raw,
            issuer=self.issuer,
            resource=self.resource,
            expected_role=self.role,
            jwks_url=self.jwks_url,
            program_is_active=(
                lambda jti, subject, audience: False
            ),
        )

        if identity is None:
            return None

        return AccessToken(
            token=raw,
            client_id=identity.client_id,
            subject=identity.subject,
            resource=self.resource,
            scopes=[self.role],
            expires_at=identity.expires_at,
            claims={
                "iss": self.issuer,
                "subject": identity.subject,
                "role": identity.role,
                "mobile": identity.mobile,
                "officer_username":
                    identity.officer_username,
            },
        )


def create_mcp(name, role):
    issuer = required(
        "PUBLIC_BASE_URL"
    ).rstrip("/")

    resource = issuer + "/mcp/" + role

    return MCPServer(
        name,
        token_verifier=PortalTokenVerifier(
            role,
            resource,
            issuer,
            required("MCP_JWKS_URL"),
        ),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer),
            resource_server_url=AnyHttpUrl(resource),
            required_scopes=[role],
            validate_token_resource=True,
        ),
    )


def require_identity(role):
    token = get_access_token()
    claims = token.claims if token else None

    if not isinstance(claims, dict):
        raise PermissionError("Authentication required")

    if claims.get("role") != role:
        raise PermissionError(
            "Not authenticated for this role"
        )

    key = (
        "mobile"
        if role == "citizen"
        else "officer_username"
    )

    value = claims.get(key)

    if (
        not isinstance(value, str)
        or token.subject != role + ":" + value
    ):
        raise PermissionError(
            "Invalid authenticated identity"
        )

    return value


def streamable_app(mcp):
    public = required(
        "PUBLIC_BASE_URL"
    ).rstrip("/")

    hostname = urlsplit(public).hostname

    if not hostname:
        raise RuntimeError("Invalid public hostname")

    security = TransportSecuritySettings(
        allowed_hosts=[
            hostname,
            hostname + ":*",
        ],
        allowed_origins=[
            public,
        ],
    )

    return mcp.streamable_http_app(
        transport_security=security
    )
