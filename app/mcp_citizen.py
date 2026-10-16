#This creates five Citizen MCP tools, up from two.
"""Citizen MCP server: narrow, read-only, verified-owner access."""

"""Citizen MCP tools with verified OAuth identity."""

from app import get_db

from mcp_repository import (
    citizen_applications,
    citizen_application_status,
)

from mcp_runtime import (
    create_mcp,
    require_identity,
    streamable_app,
)

from mcp_actions import (
    scheme_requirements,
    submit_as_citizen,
    withdraw_as_citizen,
)


mcp = create_mcp("Seva Setu Citizen", "citizen")


@mcp.tool()
def get_scheme_requirements() -> dict:
    """Get eligibility, deadline, upload instructions and required fields."""
    require_identity("citizen")
    return scheme_requirements()


@mcp.tool()
def list_my_applications() -> list[dict]:
    """Show applications belonging to the authenticated citizen only."""
    return citizen_applications(
        get_db,
        require_identity("citizen"),
    )


@mcp.tool()
def get_my_application_status(
    application_no: str,
) -> dict:
    """Look up an owned application by public reference."""
    return citizen_application_status(
        get_db,
        require_identity("citizen"),
        application_no,
    )


@mcp.tool()
def submit_pension_application(
    applicant_name: str,
    dob: str,
    village: str,
    block: str,
    bank_account: str,
    ifsc: str,
    document_ticket: str,
    confirm_submission: bool = False,
    gender: str = "",
    marital_status: str = "",
    husband_name: str = "",
) -> dict:
    """Submit a pension application after explicit user confirmation.

    Ask for missing information. Never invent personal or bank details.
    DOB must be DD/MM/YYYY.
    Citizen must upload age proof through the verified portal.
    """

    owner = require_identity("citizen")

    data = {
        "applicant_name": applicant_name,
        "dob": dob,
        "village": village,
        "block": block,
        "bank_account": bank_account,
        "ifsc": ifsc,
        "gender": gender,
        "marital_status": marital_status,
        "husband_name": husband_name,
    }

    return submit_as_citizen(
        owner,
        data,
        document_ticket,
        confirm_submission,
    )


@mcp.tool()
def withdraw_my_application(
    application_no: str,
    confirm_withdrawal: bool = False,
) -> dict:
    """Withdraw an owned pending application after confirmation."""
    return withdraw_as_citizen(
        require_identity("citizen"),
        application_no,
        confirm_withdrawal,
    )


app = streamable_app(mcp)
