
"""MCP v2 Streamable HTTP evaluation client.

Only connects to explicitly configured endpoint URLs.
No bearer token is written to evaluation reports.
"""

import json
from urllib.parse import urlsplit

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class EvaluationClientError(Exception):
    pass


def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        if not (
            parsed.scheme == "http"
            and parsed.hostname in ("localhost", "127.0.0.1")
        ):
            raise EvaluationClientError(
                "MCP evaluation requires HTTPS outside localhost"
            )
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise EvaluationClientError("Invalid MCP endpoint URL")
    return url


def normalize_result(result):
    """Convert MCP tool output to ordinary Python data."""
    if result.isError:
        raise EvaluationClientError("MCP tool reported an error")

    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    values = []
    for item in result.content:
        text = getattr(item, "text", None)
        if text is None:
            continue
        try:
            values.append(json.loads(text))
        except (TypeError, ValueError):
            values.append(text)

    if len(values) == 1:
        return values[0]
    return values


async def call_tool(url, token, tool_name, arguments=None):
    """Connect, authenticate, initialize and invoke one MCP tool."""
    validate_url(url)

    if not token:
        raise EvaluationClientError("Missing evaluation access token")

    if not tool_name or not isinstance(tool_name, str):
        raise EvaluationClientError("Invalid tool name")

    headers = {"Authorization": "Bearer " + token}

    timeout = httpx2.Timeout(30.0, read=120.0)

    async with httpx2.AsyncClient(
        headers=headers,
        timeout=timeout,
        follow_redirects=False,
    ) as http_client:

        async with streamable_http_client(
            url,
            http_client=http_client,
        ) as (read_stream, write_stream):

            async with ClientSession(
                read_stream, write_stream
            ) as session:

                await session.initialize()

                available = await session.list_tools()
                names = {tool.name for tool in available.tools}

                if tool_name not in names:
                    raise EvaluationClientError(
                        "Expected MCP tool was not advertised"
                    )

                result = await session.call_tool(
                    tool_name,
                    arguments=arguments or {},
                )
                return normalize_result(result)
