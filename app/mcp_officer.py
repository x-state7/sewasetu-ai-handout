
"""Officer MCP server: authenticated read-only operational summaries."""
from mcp_runtime import create_mcp, require_identity
from mcp_repository import officer_queue, officer_counts, officer_status
from app import get_db

mcp = create_mcp('Seva Setu Officer', 'officer')


@mcp.tool()
def pending_application_queue(limit: int = 25) -> list[dict]:
    """View a small pending-work queue without bank or identity details."""
    require_identity('officer')
    return officer_queue(get_db, limit)


@mcp.tool()
def application_status(application_no: str) -> dict:
    """View operational status of one application."""
    require_identity('officer')
    if not isinstance(application_no, str) or not (1 <= len(application_no) <= 40):
        raise ValueError('Invalid application number')
    return officer_status(get_db, application_no)


@mcp.tool()
def application_status_counts() -> dict:
    """Return per-status application counts."""
    require_identity('officer')
    return officer_counts(get_db)

app = mcp.streamable_http_app()
