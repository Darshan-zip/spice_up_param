-- Local PostgreSQL schema for the spice monitor.
-- Run as the spice_app user:
--   psql -h 127.0.0.1 -U spice_app -d spice_db -f sql/postgres_schema.sql

CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGSERIAL PRIMARY KEY,

    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    pressure DOUBLE PRECISION,

    mq135_ppm DOUBLE PRECISION,
    cjmcuvoc_raw DOUBLE PRECISION,
    voc_voltage DOUBLE PRECISION,

    red INTEGER,
    green INTEGER,
    blue INTEGER,
    clear INTEGER,

    color_temp DOUBLE PRECISION,
    lux DOUBLE PRECISION,

    dew_point DOUBLE PRECISION,
    absolute_humidity DOUBLE PRECISION,
    heat_index DOUBLE PRECISION,

    mq_rate DOUBLE PRECISION,
    voc_rate DOUBLE PRECISION,

    mold_risk DOUBLE PRECISION,
    environmental_stress DOUBLE PRECISION,
    storage_safety_score DOUBLE PRECISION,

    aroma_index DOUBLE PRECISION,
    color_index DOUBLE PRECISION,
    oxidation_index DOUBLE PRECISION,

    raw_payload JSONB,

    supabase_synced BOOLEAN NOT NULL DEFAULT FALSE
);

-- Migration for databases created before the sync flag existed.
ALTER TABLE sensor_readings
    ADD COLUMN IF NOT EXISTS supabase_synced
    BOOLEAN NOT NULL DEFAULT FALSE;

-- Speeds up the "find rows that still need syncing" query.
CREATE INDEX IF NOT EXISTS idx_sensor_readings_supabase_pending
    ON sensor_readings (id)
    WHERE supabase_synced = FALSE;
