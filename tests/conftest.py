from __future__ import annotations

import sqlite3

import pytest


@pytest.fixture
def sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
