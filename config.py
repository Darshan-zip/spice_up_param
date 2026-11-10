"""Shared configuration loaded from the project .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None or value == "":
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {value!r}") from exc


# ------------------------------------------------------------
# Supabase
# ------------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "thermal-captures")
SUPABASE_TABLE = os.getenv("SUPABASE_TABLE", "sensor_readings")

# ------------------------------------------------------------
# MQTT
# ------------------------------------------------------------

MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = _env_int("MQTT_PORT", 1883)
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "spice_db_receiver")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "spice/sensor/data")

# ------------------------------------------------------------
# PostgreSQL
# ------------------------------------------------------------

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = _env_int("DB_PORT", 5432)
DB_NAME = os.getenv("DB_NAME", "spice_db")
DB_USER = os.getenv("DB_USER", "spice_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# ------------------------------------------------------------
# Service intervals
# ------------------------------------------------------------

CAPTURE_INTERVAL = _env_int("CAPTURE_INTERVAL", 30)
SYNC_INTERVAL = _env_int("SYNC_INTERVAL", 60)
SYNC_BATCH_SIZE = _env_int("SYNC_BATCH_SIZE", 100)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------


def get_supabase():
    """Create a Supabase client on demand."""

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in the .env file."
        )

    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)
