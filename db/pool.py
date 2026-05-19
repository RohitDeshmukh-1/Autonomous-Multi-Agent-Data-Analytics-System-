"""
db/pool.py
Thread-safe connection pool for Neon Postgres.

Instead of opening a fresh TLS connection on every node (200-500ms each),
we maintain a pool of warm connections. This saves 1-2 seconds per query
when the agent traverses 5-6 nodes that all need DB access.

PERFORMANCE OPTIMIZATION: Added dynamic connection pooling for custom database URIs.
This prevents the 10+ second TLS handshake on custom Railway/RDS databases when
executing the generated code.
"""

import os
import hashlib
from contextlib import contextmanager
from functools import lru_cache
from threading import Lock

import psycopg2
import psycopg2.pool
import psycopg2.extras

_pool_lock = Lock()
_pool = None

# Dynamic pool registry for custom user databases
_dynamic_pools_lock = Lock()
_dynamic_pools = {}


def get_pool(db_url: str = None) -> psycopg2.pool.ThreadedConnectionPool:
    """
    Lazily create a global threaded connection pool.
    If db_url is provided, manages a dynamic pool for that specific database.
    """
    if db_url is None:
        global _pool
        if _pool is None or _pool.closed:
            with _pool_lock:
                if _pool is None or _pool.closed:
                    default_url = os.environ["NEON_DATABASE_URL"]
                    _pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=10,
                        dsn=default_url,
                    )
        return _pool
    else:
        # Securely hash the URL for the registry key
        pool_key = hashlib.sha256(db_url.encode()).hexdigest()
        
        with _dynamic_pools_lock:
            if pool_key not in _dynamic_pools or _dynamic_pools[pool_key].closed:
                _dynamic_pools[pool_key] = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=5,
                    dsn=db_url,
                )
            return _dynamic_pools[pool_key]


def get_connection(db_url: str = None):
    """Get a connection from the pool."""
    return get_pool(db_url).getconn()


def release_connection(conn, db_url: str = None):
    """Return a connection to the pool."""
    try:
        get_pool(db_url).putconn(conn)
    except Exception:
        pass  # Pool may have been closed during shutdown


@contextmanager
def pooled_connection(readonly: bool = False, db_url: str = None):
    """
    Context manager for pooled database connections.
    Automatically returns the connection to the pool on exit.

    Usage:
        with pooled_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = get_connection(db_url)
    try:
        if readonly:
            conn.set_session(readonly=True, autocommit=True)
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        # Reset session to writable for the next user if not readonly
        if not readonly:
            try:
                conn.set_session(readonly=False, autocommit=False)
            except Exception:
                pass
        release_connection(conn, db_url)


@contextmanager
def pooled_cursor(readonly: bool = False, dict_cursor: bool = False, db_url: str = None):
    """
    Convenience: yields a cursor directly.

    Usage:
        with pooled_cursor(dict_cursor=True) as (cur, conn):
            cur.execute("SELECT * FROM users")
            rows = cur.fetchall()
    """
    with pooled_connection(readonly=readonly, db_url=db_url) as conn:
        factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        with conn.cursor(cursor_factory=factory) as cur:
            yield cur, conn
