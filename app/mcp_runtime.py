
"""OAuth adapter: independently validates every MCP request using Step 1 auth core."""
import os
from pydantic import AnyHttpUrl
from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp_auth import verify_mcp_token


def _required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise RuntimeError(f'Missing environment variable: {name}')
    return value


def _program_is_active(jti, subject, resource):
    """Fail closed. Implement database check before enabling program tokens."""
    return False


class PortalTokenVerifier(TokenVerifier):
    def __init__(self, role, resource, issuer, jwks_url):
        self.role, self.resource = role, resource
        self.issuer, self.jwks_url = issuer, jwks_url

    async def verify_token(self, token):
        identity = verify_mcp_token(
            token, issuer=self.issuer, resource=self.resource,
            expected_role=self.role, jwks_url=self.jwks_url,
            program_is_active=_program_is_active)
        if identity is None:
            return None
        return AccessToken(
            token=token, client_id=identity.client_id,
            scopes=[self.role], resource=self.resource,
            expires_at=identity.expires_at,
            claims={'subject': identity.subject, 'role': identity.role,
                    'mobile': identity.mobile,
                    'officer_username': identity.officer_username})


def create_mcp(name, role):
    issuer = _required('PUBLIC_BASE_URL').rstrip('/')
    # Exact public URL is also used as OAuth JWT audience.
    resource = issuer + '/mcp/' + role
    verifier = PortalTokenVerifier(role, resource, issuer, _required('MCP_JWKS_URL'))
    server = MCPServer(
        name,
        token_verifier=verifier,
        auth=AuthSettings(issuer_url=AnyHttpUrl(issuer),
                          resource_server_url=AnyHttpUrl(resource),
                          required_scopes=[role], validate_token_resource=True))
    return server


def require_identity(role):
    access = get_access_token()
    claims = getattr(access, 'claims', None) if access else None
    if not isinstance(claims, dict) or claims.get('role') != role:
        raise PermissionError('Authentication required')
    subject = claims.get('subject')
    value = claims.get('mobile' if role == 'citizen' else 'officer_username')
    if not value or subject != f'{role}:{value}':
        raise PermissionError('Invalid identity')
    return value
