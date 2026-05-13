"""
db/pool.py
Thread-safe connection pool for Neon Postgres.

Instead of opening a fresh TLS connection on every node (200-500ms each),
we maintain a pool of warm connections. This saves 1-2 seconds per query
when the agent traverses 5-6 nodes that all need DB access.
"""

import os
from contextlib import contextmanager
from functools import lru_cache
from threading import Lock

import psycopg2
import psycopg2.pool
import psycopg2.extras

_pool_lock = Lock()
_pool = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Lazily create a global threaded connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        with _pool_lock:
            if _pool is None or _pool.closed:
                db_url = os.environ["NEON_DATABASE_URL"]
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    dsn=db_url,
                )
    return _pool


def get_connection():
    """Get a connection from the pool."""
    return get_pool().getconn()


def release_connection(conn):
    """Return a connection to the pool."""
    try:
        get_pool().putconn(conn)
    except Exception:
        pass  # Pool may have been closed during shutdown


@contextmanager
def pooled_connection(readonly: bool = False):
    """
    Context manager for pooled database connections.
    Automatically returns the connection to the pool on exit.

    Usage:
        with pooled_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = get_connection()
    try:
        if readonly:
            conn.set_session(readonly=True, autocommit=True)
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        # Reset session to writable for the next user
        try:
            conn.set_session(readonly=False, autocommit=False)
        except Exception:
            pass
        release_connection(conn)


@contextmanager
def pooled_cursor(readonly: bool = False, dict_cursor: bool = False):
    """
    Convenience: yields a cursor directly.

    Usage:
        with pooled_cursor(dict_cursor=True) as (cur, conn):
            cur.execute("SELECT * FROM users")
            rows = cur.fetchall()
    """
    with pooled_connection(readonly=readonly) as conn:
        factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        with conn.cursor(cursor_factory=factory) as cur:
            yield cur, conn
