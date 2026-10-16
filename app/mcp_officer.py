
#This creates five Officer tools, up from three.
#The Citizen and Officer tools remain separate. The authenticated identity comes from the 
#verified OAuth access token, not an AI-supplied mobile number or officer username.
"""Department-officer MCP tools with block restrictions."""

from contextlib import closing

from app import get_db

from mcp_runtime import (
    create_mcp,
    require_identity,
    streamable_app,
)

from mcp_actions import (
    officer_queue,
    officer_detail,
    officer_decide,
    _blocks,
)


mcp = create_mcp("Seva Setu Officer", "officer")


@mcp.tool()
def pending_application_queue(
    limit: int = 20,
) -> list[dict]:
    """List oldest pending applications in assigned blocks."""
    require_identity("officer")
    return officer_queue(limit)


@mcp.tool()
def application_status(
    application_no: str,
) -> dict:
    """Review an assigned-block application and its audit history."""
    require_identity("officer")
    return officer_detail(application_no)


@mcp.tool()
def application_status_counts() -> dict:
    """Count application statuses in assigned blocks only."""
    require_identity("officer")

    with closing(get_db()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, COUNT(*)
                FROM applications
                WHERE block = ANY(%s)
                GROUP BY status
                """,
                (_blocks(),),
            )
            return dict(cur.fetchall())


@mcp.tool()
def approve_application(
    application_no: str,
    confirm_decision: bool = False,
    note: str = "",
) -> dict:
    """Approve a reviewed pending case after officer confirmation."""
    officer = require_identity("officer")

    return officer_decide(
        application_no,
        "APPROVED",
        officer,
        note,
        confirm_decision,
    )


@mcp.tool()
def reject_application(
    application_no: str,
    reason: str,
    confirm_decision: bool = False,
) -> dict:
    """Reject a pending case with a reason and officer confirmation."""
    officer = require_identity("officer")

    return officer_decide(
        application_no,
        "REJECTED",
        officer,
        reason,
        confirm_decision,
    )


app = streamable_app(mcp)
