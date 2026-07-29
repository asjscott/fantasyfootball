from contextlib import contextmanager

import psycopg

from ml.config import require_database_url


@contextmanager
def get_connection():
    conn = psycopg.connect(require_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
