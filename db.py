"""PostgreSQL connection helper."""

import psycopg

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


def get_db_connection():
    """Return a new PostgreSQL connection."""

    if not DB_PASSWORD:
        raise RuntimeError("DB_PASSWORD must be set in the .env file.")

    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
