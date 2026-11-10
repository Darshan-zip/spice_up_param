#pragma once

// Copy this file to secrets.h and fill in your own values.
// secrets.h is ignored by git and must never be committed.

#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Use the Raspberry Pi's LAN IP address, not 127.0.0.1.
#define MQTT_SERVER "192.168.1.50"
#define MQTT_PORT 1883

#define MQTT_USER "spice_mqtt_user"
#define MQTT_PASSWORD "YOUR_ESP32_MQTT_PASSWORD"
#define MQTT_TOPIC "spice/sensor/data"
