
"""Offline Step 7 checks; no database required."""

from mcp_document_claims import _hash


def test_invalid_ticket_format():
    assert _hash("../") is None
    assert _hash("abc") is None


def test_ticket_hash_does_not_expose_secret():
    ticket = "A" * 43

    digest = _hash(ticket)

    assert digest is not None
    assert len(digest) == 64
    assert ticket not in digest
