
"""Read-only, parameterized SQL queries for Seva Setu MCP. No PII in outputs."""
from contextlib import closing


def _rows(connect, sql, params=()):
    with closing(connect()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def citizen_applications(connect, mobile):
    """Mobile MUST come from a verified bearer token, never tool arguments."""
    rows = _rows(connect, """
        SELECT application_no, status, submitted_at, decided_at
        FROM applications WHERE mobile = %s
        ORDER BY submitted_at DESC, id DESC LIMIT 20
    """, (mobile,))
    return [{"application_no": r[0], "status": r[1],
             "submitted_at": r[2].isoformat() if r[2] else None,
             "decided_at": r[3].isoformat() if r[3] else None} for r in rows]


def citizen_application_status(connect, mobile, application_no):
    rows = _rows(connect, """
        SELECT application_no, status, submitted_at, decided_at
        FROM applications WHERE mobile = %s AND application_no = %s
        LIMIT 1
    """, (mobile, application_no))
    if not rows:
        return {"found": False}
    r = rows[0]
    return {"found": True, "application_no": r[0], "status": r[1],
            "submitted_at": r[2].isoformat() if r[2] else None,
            "decided_at": r[3].isoformat() if r[3] else None}


def officer_queue(connect, limit=25):
    limit = max(1, min(int(limit), 50))
    rows = _rows(connect, """
        SELECT application_no, status, submitted_at, village, block
        FROM applications WHERE status = 'PENDING'
        ORDER BY submitted_at ASC, id ASC LIMIT %s
    """, (limit,))
    return [{"application_no": r[0], "status": r[1],
             "submitted_at": r[2].isoformat() if r[2] else None,
             "village": r[3], "block": r[4]} for r in rows]


def officer_counts(connect):
    rows = _rows(connect, """
        SELECT status, COUNT(*) FROM applications GROUP BY status ORDER BY status
    """)
    return {str(status): count for status, count in rows}


def officer_status(connect, application_no):
    rows = _rows(connect, """
        SELECT application_no, status, submitted_at, decided_at, village, block
        FROM applications WHERE application_no = %s LIMIT 1
    """, (application_no,))
    if not rows:
        return {"found": False}
    r = rows[0]
    return {"found": True, "application_no": r[0], "status": r[1],
            "submitted_at": r[2].isoformat() if r[2] else None,
            "decided_at": r[3].isoformat() if r[3] else None,
            "village": r[4], "block": r[5]}
