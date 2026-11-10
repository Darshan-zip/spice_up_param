# Spice Up Param

Environmental and thermal monitoring stack for a spice storage area.

The Raspberry Pi receives sensor readings from an ESP32 over MQTT, stores
them in a local PostgreSQL database, and synchronizes them to Supabase.
Separately, a Raspberry Pi camera and an MLX90640 thermal camera capture
normal/thermal images and upload them to Supabase Storage.

---

## 1. Architecture

```text
ESP32 sensors
     |
     | MQTT JSON on spice/sensor/data
     v
Mosquitto broker (Raspberry Pi)
     |
     | spice_db_receiver
     v
receiver.py  ---------------------------> PostgreSQL (local, authoritative)
     |                                         |
     | immediate best-effort sync              | pending rows retried every 60 s
     v                                         v
Supabase table <----------------------- supabase_sync.py
public.sensor_readings

Raspberry Pi camera + MLX90640
     |
     v
capture_and_upload.py  --------------> Supabase Storage bucket
```

Why local first: if Wi-Fi or Supabase is unavailable, readings are still
saved on the Pi. A `supabase_synced` flag tracks which rows have reached
the cloud. Uploads use an upsert on `id`, so retries cannot create
duplicates.

---

## 2. Project files

| File | Purpose |
| --- | --- |
| `config.py` | Loads `.env`, exposes shared settings, creates the Supabase client |
| `db.py` | Creates PostgreSQL connections |
| `receiver.py` | Subscribes to MQTT, inserts readings into PostgreSQL, starts an immediate Supabase sync |
| `supabase_sync.py` | Retries all rows where `supabase_synced = FALSE` |
| `capture_and_upload.py` | Captures a normal photo and a thermal frame every 30 s, uploads both |
| `upload_images.py` | Backfill utility for existing local capture images |
| `thermal_test.py` | Standalone MLX90640 test |
| `esp32/spice_sensor_node/spice_sensor_node.ino` | ESP32 sketch: reads sensors and publishes MQTT JSON |
| `esp32/spice_sensor_node/secrets.example.h` | Template for Wi-Fi and MQTT credentials; copy to `secrets.h` |
| `sql/postgres_schema.sql` | Local PostgreSQL table, migration, and index |
| `sql/supabase_schema.sql` | Supabase table |
| `mosquitto/spice.conf` | Mosquitto listener/auth configuration |
| `mosquitto/acl` | Topic permissions for the ESP32 and receiver users |
| `systemd/` | Services for the receiver, sync worker, and camera capture |
| `.env.example` | Template for all credentials and settings |
| `requirements.txt` | Python dependencies |

---

## 3. Hardware and OS assumptions

- Raspberry Pi running Raspberry Pi OS Bookworm (64-bit recommended)
- MLX90640 thermal camera on I2C (default address `0x33`)
- Raspberry Pi camera module supported by `rpicam-still`
- ESP32 sensor node with BME280, MQ135, CJMCU VOC, and TCS34725 sensors
- A Supabase project
- Python 3.11 or newer

Enable I2C and the camera:

```bash
sudo raspi-config
# Interface Options -> I2C -> Yes
# Interface Options -> Camera -> Yes (if your image exposes this menu)
sudo reboot
```

Verify the hardware:

```bash
i2cdetect -y 1          # MLX90640 should appear at 0x33
rpicam-still -o test.jpg
```

If `rpicam-still` is missing, install the camera apps:

```bash
sudo apt install -y rpicam-apps
```

The capture script also falls back to `libcamera-still` when available.

---

## 4. Program the ESP32 sensor node

The sketch is in `esp32/spice_sensor_node/`. It reads the sensors, computes
the derived indexes, and publishes a JSON message to
`spice/sensor/data` every 10 seconds.

### Wiring

| Device | ESP32 connection | Address / signal |
| --- | --- | --- |
| BME280 | I2C: SDA GPIO 21, SCL GPIO 22 | `0x77`, fallback `0x76` |
| TCS34725 | I2C: SDA GPIO 21, SCL GPIO 22 | `0x29` |
| MQ135 | GPIO 32 | analog input |
| CJMCU VOC | GPIO 33 | analog input |

The ESP32 ADC accepts 0 to 3.3 V. If an analog sensor module can output
more than 3.3 V, use a voltage divider before connecting it to the ESP32.

### Install the Arduino libraries

In Arduino IDE, open **Library Manager** and install:

- **PubSubClient** by Nick O'Leary
- **ArduinoJson 6.x** (the sketch uses `StaticJsonDocument`)
- **Adafruit Unified Sensor**
- **Adafruit BME280 Library**
- **Adafruit TCS34725**
- **MQ135** by GeorgK

Install ESP32 board support through **Boards Manager**. If the ESP32
package is not listed, add this URL in **Preferences -> Additional Boards
Manager URLs**:

```text
https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

Then install **esp32 by Espressif Systems**.

### Configure Wi-Fi and MQTT

The sketch reads credentials from `secrets.h`, which is excluded from git.
Create it from the template:

```bash
cd esp32/spice_sensor_node
cp secrets.example.h secrets.h
```

Edit `secrets.h`:

```cpp
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

#define MQTT_SERVER "192.168.1.50"   // Raspberry Pi LAN IP
#define MQTT_PORT 1883

#define MQTT_USER "spice_mqtt_user"
#define MQTT_PASSWORD "YOUR_ESP32_MQTT_PASSWORD"
#define MQTT_TOPIC "spice/sensor/data"
```

Use the Raspberry Pi's LAN IP address. `127.0.0.1` would point the ESP32
at itself, not at the Pi. The ESP32 and the Pi must be on the same network,
and the Pi firewall must allow TCP port 1883.

`MQTT_USER` and `MQTT_PASSWORD` are the `spice_mqtt_user` credentials
created in the Mosquitto section. Do not use the receiver password here.

### Upload the sketch

1. Select **Tools -> Board -> ESP32 Arduino -> ESP32 Dev Module**.
2. Select the correct serial port.
3. Open `spice_sensor_node.ino`.
4. Click **Upload**.
5. Open the Serial Monitor at **115200 baud**.

Expected startup output includes the Wi-Fi IP address, sensor
initialization results, and then `SUCCESS: MQTT message published.` every
10 seconds.

If MQTT fails:

- State `4` or `5`: wrong MQTT username/password or ACL.
- State `-2`: broker unreachable; verify `MQTT_SERVER` and port 1883.
- State `-1`: connection timeout; check that the Pi is reachable.
- Wi-Fi failure: verify SSID, password, and 2.4 GHz network availability.

Once the ESP32 is publishing, the Raspberry Pi `receiver.py` will store
each message in PostgreSQL and sync it to Supabase.

---

## 5. Install system packages

```bash
sudo apt update
sudo apt install -y \
  python3-pip \
  python3-venv \
  python3-numpy \
  mosquitto \
  mosquitto-clients \
  postgresql \
  postgresql-client \
  rpicam-apps
```

`python3-opencv` is not required by this codebase. Install it only if you
add OpenCV-based processing later.

---

## 6. Create the Python environment

Copy the project files to the Pi, for example to `~/spice_monitor`:

```bash
mkdir -p ~/spice_monitor
cd ~/spice_monitor
# copy all project files into this directory

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

`adafruit-blinka` provides `board` and `busio`. Run the scripts from the
activated virtual environment so the same interpreter sees the packages.

Quick import check:

```bash
python -c "import board, busio, adafruit_mlx90640; print('Blinka OK')"
```

---

## 7. Configure `.env`

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

Fill in:

- `SUPABASE_URL` and `SUPABASE_KEY`
- `SUPABASE_BUCKET` (default `thermal-captures`)
- `MQTT_PASSWORD` for the `spice_db_receiver` user
- `DB_PASSWORD` for the `spice_app` database user
- Optionally adjust the intervals

Use the Supabase **service_role** key on the Pi. Do not use it in a
browser or mobile app, and never commit `.env`.

---

## 8. Set up local PostgreSQL

```bash
sudo systemctl enable --now postgresql
```

Create the user and database:

```bash
sudo -u postgres psql
```

```sql
CREATE USER spice_app WITH PASSWORD 'choose-a-strong-db-password';
CREATE DATABASE spice_db OWNER spice_app;
\q
```

Create the table and index:

```bash
psql -h 127.0.0.1 -U spice_app -d spice_db -f sql/postgres_schema.sql
```

`postgres_schema.sql` is safe to re-run. It creates the table if needed,
adds `supabase_synced` if an older database is missing it, and creates
the partial index used by the retry worker.

Verify:

```bash
psql -h 127.0.0.1 -U spice_app -d spice_db -c "\d sensor_readings"
```

---

## 9. Set up Mosquitto

```bash
sudo systemctl enable --now mosquitto
```

Create the two MQTT users:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd spice_mqtt_user
sudo mosquitto_passwd /etc/mosquitto/passwd spice_db_receiver
```

Use different strong passwords. The ESP32 uses `spice_mqtt_user`; the Pi
receiver uses `spice_db_receiver`. Put the receiver password in `.env`
as `MQTT_PASSWORD`.

Install the ACL and listener configuration:

```bash
sudo cp mosquitto/acl /etc/mosquitto/acl
sudo cp mosquitto/spice.conf /etc/mosquitto/conf.d/spice.conf

sudo chown root:mosquitto /etc/mosquitto/passwd /etc/mosquitto/acl
sudo chmod 640 /etc/mosquitto/passwd /etc/mosquitto/acl

sudo systemctl restart mosquitto
sudo systemctl status mosquitto --no-pager
```

The ACL grants:

- `spice_mqtt_user`: write to `spice/sensor/data`
- `spice_db_receiver`: read from `spice/sensor/data`

Test in two terminals:

```bash
# Terminal A
mosquitto_sub \
  -h 127.0.0.1 \
  -p 1883 \
  -u spice_db_receiver \
  -P 'YOUR_DB_RECEIVER_MQTT_PASSWORD' \
  -t spice/sensor/data \
  -v
```

```bash
# Terminal B
mosquitto_pub \
  -h 127.0.0.1 \
  -p 1883 \
  -u spice_mqtt_user \
  -P 'YOUR_ESP32_MQTT_PASSWORD' \
  -t spice/sensor/data \
  -m '{"temperature":28.5,"humidity":65.2}'
```

Terminal A should print the message. If it does not, check the password
file permissions, the ACL, and `allow_anonymous false`.

---

## 10. Set up Supabase

1. Create a Supabase project.
2. Open **SQL Editor** and run `sql/supabase_schema.sql`.
3. Open **Storage** and create a bucket named `thermal-captures`.
   - Use a private bucket for production. Dashboard image links then
     need signed URLs.
   - Use a public bucket only if you intentionally want public images.
4. Open **Project Settings -> API** and copy:
   - Project URL -> `SUPABASE_URL`
   - `service_role` key -> `SUPABASE_KEY`

The cloud table intentionally uses `id BIGINT PRIMARY KEY` without an
identity default. The Raspberry Pi's local PostgreSQL id is authoritative,
which lets the upsert update an existing row instead of creating a new one.

---

## 11. Test the cameras

Activate the environment first:

```bash
cd ~/spice_monitor
source .venv/bin/activate
```

Thermal camera:

```bash
python thermal_test.py
```

Normal camera:

```bash
rpicam-still -o test.jpg
```

Full capture and upload loop:

```bash
python capture_and_upload.py
```

A successful run creates files under `thermal_captures/` and prints
Supabase upload confirmations.

---

## 12. Run the data pipeline manually

Use three terminals, all with the virtual environment activated.

```bash
# Terminal 1: MQTT -> PostgreSQL -> Supabase
python receiver.py
```

```bash
# Terminal 2: retry worker for rows that failed to sync
python supabase_sync.py
```

```bash
# Terminal 3 (optional): camera capture every 30 seconds
python capture_and_upload.py
```

Publish a test reading:

```bash
mosquitto_pub \
  -h 127.0.0.1 \
  -p 1883 \
  -u spice_mqtt_user \
  -P 'YOUR_ESP32_MQTT_PASSWORD' \
  -t spice/sensor/data \
  -m '{
    "temperature": 28.5,
    "humidity": 65.2,
    "pressure": 1008.4,
    "mq135_ppm": 12.4,
    "cjmcuvoc_raw": 830,
    "voc_voltage": 0.669,
    "red": 120,
    "green": 135,
    "blue": 110,
    "clear": 420,
    "color_temp": 4100,
    "lux": 85.3,
    "dew_point": 21.2,
    "absolute_humidity": 16.3,
    "heat_index": 29.1,
    "mq_rate": 0.15,
    "voc_rate": 2.1,
    "mold_risk": 67.1,
    "environmental_stress": 34.8,
    "storage_safety_score": 65.2,
    "aroma_index": 258.5,
    "color_index": 121.7,
    "oxidation_index": 18.7
  }'
```

Verify locally:

```bash
psql -h 127.0.0.1 -U spice_app -d spice_db \
  -c "SELECT id, received_at, temperature, humidity, supabase_synced FROM sensor_readings ORDER BY id DESC LIMIT 10;"
```

Verify in Supabase:

- Table Editor -> `sensor_readings` should contain the row.
- Storage -> `thermal-captures` should contain the uploaded images.

---

## 13. Run as systemd services

The files in `systemd/` assume:

- project directory: `/home/pi/spice_monitor`
- service user/group: `pi`
- virtual environment: `/home/pi/spice_monitor/.venv`

Edit the `User`, `Group`, `WorkingDirectory`, and `ExecStart` values if
your setup differs.

```bash
sudo cp systemd/spice-receiver.service /etc/systemd/system/
sudo cp systemd/supabase-sync.service /etc/systemd/system/
sudo cp systemd/camera-capture.service /etc/systemd/system/

sudo systemctl daemon-reload

sudo systemctl enable --now \
  spice-receiver.service \
  supabase-sync.service \
  camera-capture.service
```

Check status and logs:

```bash
systemctl status spice-receiver --no-pager
systemctl status supabase-sync --no-pager
systemctl status camera-capture --no-pager

journalctl -u spice-receiver -f
journalctl -u supabase-sync -f
journalctl -u camera-capture -f
```

The camera service sets `MPLBACKEND=Agg` because no display is available.
`capture_and_upload.py` also selects the Agg backend itself.

If the camera service cannot access the camera, make sure the service
user is in the `video` group and reboot:

```bash
sudo usermod -aG video pi
sudo reboot
```

---

## 14. Sensor payload format

The receiver accepts any JSON object and inserts known keys. Unknown keys
are preserved in `raw_payload` but are not stored in dedicated columns.

```json
{
  "temperature": 28.5,
  "humidity": 65.2,
  "pressure": 1008.4,
  "mq135_ppm": 12.4,
  "cjmcuvoc_raw": 830,
  "voc_voltage": 0.669,
  "red": 120,
  "green": 135,
  "blue": 110,
  "clear": 420,
  "color_temp": 4100,
  "lux": 85.3,
  "dew_point": 21.2,
  "absolute_humidity": 16.3,
  "heat_index": 29.1,
  "mq_rate": 0.15,
  "voc_rate": 2.1,
  "mold_risk": 67.1,
  "environmental_stress": 34.8,
  "storage_safety_score": 65.2,
  "aroma_index": 258.5,
  "color_index": 121.7,
  "oxidation_index": 18.7
}
```

Publish topic: `spice/sensor/data`.

---

## 15. Backfill old images

`upload_images.py` uploads every image in `thermal_captures/` to the
configured bucket under the `thermal/` prefix. Use it after an outage or
to upload images captured before the automatic uploader was installed:

```bash
source .venv/bin/activate
python upload_images.py
```

Because Supabase Storage rejects duplicate paths by default, already
uploaded files will be reported as failed. This is harmless.

---

## 16. Troubleshooting

**`board` or `busio` import fails**

Activate the virtual environment and reinstall Blinka:

```bash
source .venv/bin/activate
pip install --upgrade adafruit-blinka
```

**MLX90640 not detected**

- Enable I2C and reboot.
- Run `i2cdetect -y 1`; the sensor should be at `0x33`.
- Check SDA/SCL wiring and power.
- Keep the I2C bus at 800 kHz or lower.

**`rpicam-still` not found**

```bash
sudo apt install -y rpicam-apps
```

The capture script will try `libcamera-still` as a fallback. On very old
images, the legacy command is `raspistill`, which requires adapting
`camera_command()`.

**MQTT "not authorised"**

- Recreate the receiver password with `sudo mosquitto_passwd`.
- Make sure `.env` uses the `spice_db_receiver` password.
- Check `/etc/mosquitto/acl` and `conf.d/spice.conf`.
- Inspect `journalctl -u mosquitto -n 100`.

**PostgreSQL connection refused or password authentication failed**

- `sudo systemctl status postgresql`
- Confirm the user and database exist.
- Confirm `DB_PASSWORD` in `.env` matches the password set in PostgreSQL.
- Local TCP connections on `127.0.0.1` must be allowed by `pg_hba.conf`
  (the Raspberry Pi OS default is fine).

**Supabase sync fails**

Check the `supabase_sync.py` logs. Common causes:

- wrong project URL or key
- `service_role` key not used
- table or bucket missing
- network outage
- Supabase table missing `id` as primary key

Rows stay in PostgreSQL with `supabase_synced = FALSE` and are retried
every `SYNC_INTERVAL` seconds.

**Images are not in Storage**

- Confirm the bucket name matches `SUPABASE_BUCKET`.
- Confirm the key can write to Storage.
- Check that `capture_and_upload.py` printed an upload success line.
- A private bucket still accepts uploads; reading files requires signed
  URLs.

**Matplotlib fails on a headless Pi**

Both the script and the service force the `Agg` backend. If you run
matplotlib in another script, set:

```bash
export MPLBACKEND=Agg
```

**Rows are duplicated in Supabase**

Verify that `public.sensor_readings.id` is the primary key and that the
upsert uses `on_conflict="id"`. The local PostgreSQL id is the intended
shared key.

**Timestamp collision in image filenames**

The capture interval is 30 seconds, so names are unique at that rate. If
you reduce `CAPTURE_INTERVAL` below one second, include microseconds in
the timestamp.

---

## 17. Security notes

- Change every example password. Do not reuse the MQTT and database
  passwords.
- Keep `.env` at mode `600` and out of version control.
- Use the Supabase `service_role` key only on the Pi. It bypasses row
  level security.
- If your dashboard uses the public `anon` key, add appropriate RLS
  policies and keep the storage bucket private where possible.
- Mosquitto listens on port 1883 so the ESP32 can reach it. Restrict
  access with the Pi firewall so only trusted devices on the LAN can
  connect.
- `upload_images.py` and the capture service write to the same bucket;
  review the bucket's public/private setting before exposing image URLs.

---

## 18. Startup order summary

1. `mosquitto`
2. `postgresql`
3. `spice-receiver` (MQTT to database, immediate best-effort cloud sync)
4. `supabase-sync` (retry worker)
5. `camera-capture` (normal + thermal images)

All three project services can start independently. If Supabase is down,
sensor rows queue locally and images are captured locally; uploads resume
when connectivity returns (sensor rows automatically, images on the next
successful capture or via `upload_images.py`).
