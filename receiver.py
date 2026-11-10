"""MQTT receiver: store sensor data in PostgreSQL and sync to Supabase."""

import json
import logging

import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER,
    MQTT_PASSWORD,
    MQTT_PORT,
    MQTT_TOPIC,
    MQTT_USERNAME,
)
from db import get_db_connection
from supabase_sync import sync_row

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# PostgreSQL insert
# ------------------------------------------------------------


def save_sensor_data(data):
    """Insert one MQTT payload and return the new local row id."""

    query = """
        INSERT INTO sensor_readings (
            temperature,
            humidity,
            pressure,

            mq135_ppm,
            cjmcuvoc_raw,
            voc_voltage,

            red,
            green,
            blue,
            clear,

            color_temp,
            lux,

            dew_point,
            absolute_humidity,
            heat_index,

            mq_rate,
            voc_rate,

            mold_risk,
            environmental_stress,
            storage_safety_score,

            aroma_index,
            color_index,
            oxidation_index,

            raw_payload,
            supabase_synced
        )
        VALUES (
            %(temperature)s,
            %(humidity)s,
            %(pressure)s,

            %(mq135_ppm)s,
            %(cjmcuvoc_raw)s,
            %(voc_voltage)s,

            %(red)s,
            %(green)s,
            %(blue)s,
            %(clear)s,

            %(color_temp)s,
            %(lux)s,

            %(dew_point)s,
            %(absolute_humidity)s,
            %(heat_index)s,

            %(mq_rate)s,
            %(voc_rate)s,

            %(mold_risk)s,
            %(environmental_stress)s,
            %(storage_safety_score)s,

            %(aroma_index)s,
            %(color_index)s,
            %(oxidation_index)s,

            %(raw_payload)s,
            FALSE
        )
        RETURNING id
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "temperature": data.get("temperature"),
                        "humidity": data.get("humidity"),
                        "pressure": data.get("pressure"),
                        "mq135_ppm": data.get("mq135_ppm"),
                        "cjmcuvoc_raw": data.get("cjmcuvoc_raw"),
                        "voc_voltage": data.get("voc_voltage"),
                        "red": data.get("red"),
                        "green": data.get("green"),
                        "blue": data.get("blue"),
                        "clear": data.get("clear"),
                        "color_temp": data.get("color_temp"),
                        "lux": data.get("lux"),
                        "dew_point": data.get("dew_point"),
                        "absolute_humidity": data.get("absolute_humidity"),
                        "heat_index": data.get("heat_index"),
                        "mq_rate": data.get("mq_rate"),
                        "voc_rate": data.get("voc_rate"),
                        "mold_risk": data.get("mold_risk"),
                        "environmental_stress": data.get(
                            "environmental_stress"
                        ),
                        "storage_safety_score": data.get(
                            "storage_safety_score"
                        ),
                        "aroma_index": data.get("aroma_index"),
                        "color_index": data.get("color_index"),
                        "oxidation_index": data.get("oxidation_index"),
                        "raw_payload": json.dumps(data),
                    },
                )

                row_id = cur.fetchone()[0]

            conn.commit()

        logger.info(
            "Sensor data stored locally. PostgreSQL ID=%s",
            row_id,
        )

        return row_id

    except Exception:
        logger.exception("Failed to store sensor data in PostgreSQL.")
        return None


# ------------------------------------------------------------
# MQTT callbacks
# ------------------------------------------------------------


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logger.info("Connected to MQTT broker.")

        client.subscribe(MQTT_TOPIC)

        logger.info("Subscribed to: %s", MQTT_TOPIC)

    else:
        logger.error("MQTT connection failed: %s", reason_code)


def on_message(client, userdata, message):
    logger.info("MQTT message received.")

    try:
        payload = message.payload.decode("utf-8")
        data = json.loads(payload)

        if not isinstance(data, dict):
            logger.error("Payload is not a JSON object.")
            return

        # Step 1: always store locally first.
        row_id = save_sensor_data(data)

        if row_id is None:
            logger.error("Local database insert failed.")
            return

        # Step 2: try Supabase immediately. On failure the row stays
        # queued (supabase_synced = FALSE) for supabase_sync.py.
        if sync_row(row_id):
            logger.info(
                "Row %s synchronized to Supabase immediately.",
                row_id,
            )
        else:
            logger.warning(
                "Row %s could not be sent to Supabase. "
                "It remains queued for retry.",
                row_id,
            )

    except UnicodeDecodeError:
        logger.exception("Invalid UTF-8 MQTT payload.")

    except json.JSONDecodeError:
        logger.exception("Invalid JSON received.")

    except Exception:
        logger.exception("Unexpected MQTT processing error.")


def on_disconnect(
    client,
    userdata,
    disconnect_flags,
    reason_code,
    properties,
):
    logger.warning("Disconnected from MQTT broker: %s", reason_code)


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------


def main():
    if not MQTT_PASSWORD:
        raise RuntimeError("MQTT_PASSWORD must be set in the .env file.")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="raspberrypi_db_receiver",
    )

    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    client.reconnect_delay_set(min_delay=1, max_delay=30)

    logger.info("Connecting to MQTT broker...")

    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    logger.info("MQTT receiver started.")

    client.loop_forever()


if __name__ == "__main__":
    main()
