
"""Lightweight future tests; do not run on resource-constrained development PC."""
from mcp_repository import citizen_application_status, citizen_applications


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    def execute(self, sql, params=()):
        self.params = params

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Conn:
    def __init__(self, cursor):
        self.cur = cursor

    def cursor(self):
        return self.cur

    def close(self):
        pass


def test_citizen_lookup_always_uses_owner_mobile():
    cur = Cursor([])
    result = citizen_application_status(
        lambda: Conn(cur), '9999999999', 'SSP123'
    )
    assert result == {'found': False}
    assert cur.params == ('9999999999', 'SSP123')


def test_citizen_list_is_bound_to_owner():
    cur = Cursor([])
    assert citizen_applications(
        lambda: Conn(cur), '9999999999'
    ) == []
    assert cur.params == ('9999999999',)
