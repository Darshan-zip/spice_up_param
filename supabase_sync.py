"""Synchronize PostgreSQL sensor rows to Supabase.

Each local row has a ``supabase_synced`` flag. Rows are uploaded with
an upsert on ``id`` so retries never create duplicates.
"""

import json
import logging
import time

from psycopg.rows import dict_row

from config import (
    SUPABASE_TABLE,
    SYNC_BATCH_SIZE,
    SYNC_INTERVAL,
    get_supabase,
)
from db import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)

_supabase_client = None


def _supabase():
    """Lazily create and reuse the Supabase client."""

    global _supabase_client

    if _supabase_client is None:
        _supabase_client = get_supabase()

    return _supabase_client


# ------------------------------------------------------------
# Row conversion
# ------------------------------------------------------------


def prepare_supabase_row(row):
    """Convert a PostgreSQL row into a Supabase-ready dictionary."""

    payload = dict(row)

    if payload.get("received_at") is not None:
        payload["received_at"] = payload["received_at"].isoformat()

    raw_payload = payload.get("raw_payload")

    if isinstance(raw_payload, str):
        try:
            payload["raw_payload"] = json.loads(raw_payload)
        except json.JSONDecodeError:
            payload["raw_payload"] = None

    # This column only exists in the local database.
    payload.pop("supabase_synced", None)

    return payload


# ------------------------------------------------------------
# Upload one row
# ------------------------------------------------------------


def send_row_to_supabase(row):
    local_id = row["id"]

    try:
        supabase_row = prepare_supabase_row(row)

        _supabase().table(SUPABASE_TABLE).upsert(
            supabase_row,
            on_conflict="id",
        ).execute()

        logger.info("Uploaded row %s to Supabase.", local_id)
        return True

    except Exception as exc:
        logger.error(
            "Supabase upload failed for row %s: %s",
            local_id,
            exc,
        )
        return False


# ------------------------------------------------------------
# Local sync flag
# ------------------------------------------------------------


def mark_as_synced(local_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sensor_readings
                    SET supabase_synced = TRUE
                    WHERE id = %s
                    """,
                    (local_id,),
                )

            conn.commit()

        logger.info("Marked row %s as synchronized.", local_id)
        return True

    except Exception as exc:
        logger.error(
            "Failed to mark row %s as synchronized: %s",
            local_id,
            exc,
        )
        return False


# ------------------------------------------------------------
# Synchronize one row
# ------------------------------------------------------------


def sync_row(local_id):
    """Upload one row, then mark it as synchronized locally."""

    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM sensor_readings
                    WHERE id = %s
                      AND supabase_synced = FALSE
                    """,
                    (local_id,),
                )

                row = cur.fetchone()

        if row is None:
            return True

        if not send_row_to_supabase(row):
            return False

        return mark_as_synced(local_id)

    except Exception:
        logger.exception(
            "Unexpected error synchronizing row %s.",
            local_id,
        )
        return False


# ------------------------------------------------------------
# Pending rows
# ------------------------------------------------------------


def get_pending_rows():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM sensor_readings
                    WHERE supabase_synced = FALSE
                    ORDER BY id
                    LIMIT %s
                    """,
                    (SYNC_BATCH_SIZE,),
                )

                rows = cur.fetchall()

        return [row[0] for row in rows]

    except Exception:
        logger.exception("Failed to read pending rows.")
        return []


def synchronize_pending_rows():
    pending_ids = get_pending_rows()

    if not pending_ids:
        logger.info("No pending rows.")
        return

    logger.info("Found %d pending rows.", len(pending_ids))

    successful = 0
    failed = 0

    for local_id in pending_ids:
        if sync_row(local_id):
            successful += 1
        else:
            failed += 1

    logger.info(
        "Synchronization complete: %d successful, %d failed.",
        successful,
        failed,
    )


# ------------------------------------------------------------
# Main loop
# ------------------------------------------------------------


def main():
    logger.info("Supabase synchronization service started.")
    logger.info("Retry interval: %d seconds", SYNC_INTERVAL)

    while True:
        try:
            synchronize_pending_rows()
        except Exception:
            logger.exception("Unexpected synchronization error.")

        time.sleep(SYNC_INTERVAL)


if __name__ == "__main__":
    main()
