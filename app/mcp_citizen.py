
"""Citizen MCP server: narrow, read-only, verified-owner access."""
from mcp_runtime import create_mcp, require_identity
from mcp_repository import citizen_applications, citizen_application_status
from app import get_db

mcp = create_mcp('Seva Setu Citizen', 'citizen')


@mcp.tool()
def list_my_applications() -> list[dict]:
    """List the authenticated citizen's applications; no mobile argument accepted."""
    mobile = require_identity('citizen')
    return citizen_applications(get_db, mobile)


@mcp.tool()
def get_my_application_status(application_no: str) -> dict:
    """View status for an application owned by the authenticated citizen."""
    mobile = require_identity('citizen')
    if not isinstance(application_no, str) or not (1 <= len(application_no) <= 40):
        raise ValueError('Invalid application number')
    return citizen_application_status(get_db, mobile, application_no)

# Expose this ASGI application through a path-preserving reverse proxy.
app = mcp.streamable_http_app()
