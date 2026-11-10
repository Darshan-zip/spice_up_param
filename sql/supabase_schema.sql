-- Supabase / cloud PostgreSQL schema.
-- Run this in the Supabase Dashboard -> SQL Editor.

CREATE TABLE IF NOT EXISTS public.sensor_readings (
    id BIGINT PRIMARY KEY,

    received_at TIMESTAMPTZ NOT NULL,

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

    raw_payload JSONB
);

-- The local PostgreSQL id is authoritative. Do not add an identity
-- default here, otherwise the upsert on id will create new rows
-- instead of updating existing ones.

CREATE INDEX IF NOT EXISTS idx_sensor_readings_received_at
    ON public.sensor_readings (received_at DESC);
