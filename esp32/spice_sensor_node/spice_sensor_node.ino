#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_TCS34725.h>
#include "MQ135.h"
#include <math.h>

// ============================================================
// WIFI CONFIGURATION
// ============================================================

const char* ssid = "SNUC";
const char* password = "snu12345";

const char* mqtt_server = "10.31.28.157";
const char* mqtt_user = "spice_mqtt_user";
const char* mqtt_pass = "12345";
const int mqtt_port = 1883;
const char* mqtt_topic = "spice/sensor/data";

// ============================================================
// SENSOR PINS
// ============================================================

#define MQ135_PIN 32
#define CJMCU_PIN 33

#define SDA_PIN 21
#define SCL_PIN 22

// ============================================================
// OBJECTS
// ============================================================

WiFiClient espClient;
PubSubClient client(espClient);

Adafruit_BME280 bme;

Adafruit_TCS34725 tcs =
  Adafruit_TCS34725(
    TCS34725_INTEGRATIONTIME_50MS,
    TCS34725_GAIN_4X
  );

MQ135 mq135(MQ135_PIN);

// ============================================================
// PREVIOUS VALUES
// ============================================================

float prevMQ = 0;
float prevVOC = 0;

unsigned long prevTime = 0;


// ============================================================
// WIFI CONNECTION
// ============================================================

void setup_wifi() {

  Serial.println();
  Serial.println("========================================");
  Serial.println("WIFI CONNECTION");
  Serial.println("========================================");

  Serial.print("SSID: ");
  Serial.println(ssid);

  Serial.println("Connecting to Wi-Fi...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);

    Serial.print(".");

    attempts++;

    if (attempts >= 60) {

      Serial.println();
      Serial.println("ERROR: Wi-Fi connection failed.");
      Serial.println("Check:");
      Serial.println("1. SSID");
      Serial.println("2. Password");
      Serial.println("3. Wi-Fi availability");

      return;
    }
  }

  Serial.println();
  Serial.println("Wi-Fi connected!");

  Serial.print("ESP32 IP address: ");
  Serial.println(WiFi.localIP());

  Serial.print("Gateway: ");
  Serial.println(WiFi.gatewayIP());

  Serial.print("Signal strength RSSI: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
}


// ============================================================
// MQTT CONNECTION
// ============================================================

bool connectMQTT() {

  Serial.println();
  Serial.println("========================================");
  Serial.println("MQTT CONNECTION");
  Serial.println("========================================");

  Serial.print("MQTT server: ");
  Serial.println(mqtt_server);

  Serial.print("MQTT port: ");
  Serial.println(mqtt_port);

  Serial.print("MQTT username: ");
  Serial.println(mqtt_user);

  Serial.print("MQTT topic: ");
  Serial.println(mqtt_topic);

  Serial.println();
  Serial.println("Attempting MQTT connection...");

  // Unique client ID
  String clientId = "ESP32Client-";
  clientId += String((uint32_t)ESP.getEfuseMac(), HEX);

  Serial.print("Client ID: ");
  Serial.println(clientId);

  if (client.connect(
        clientId.c_str(),
        mqtt_user,
        mqtt_pass
      )) {

    Serial.println("MQTT CONNECTED!");

    return true;
  }

  Serial.println("MQTT CONNECTION FAILED.");

  Serial.print("MQTT state code: ");
  Serial.println(client.state());

  Serial.println();
  Serial.println("MQTT state meanings:");
  Serial.println("-2 = MQTT_CONNECT_FAILED");
  Serial.println("-1 = MQTT_CONNECTION_TIMEOUT");
  Serial.println(" 0 = MQTT_CONNECTED");
  Serial.println(" 1 = MQTT_CONNECT_BAD_PROTOCOL");
  Serial.println(" 2 = MQTT_CONNECT_BAD_CLIENT_ID");
  Serial.println(" 3 = MQTT_CONNECT_UNAVAILABLE");
  Serial.println(" 4 = MQTT_CONNECT_BAD_CREDENTIALS");
  Serial.println(" 5 = MQTT_CONNECT_UNAUTHORIZED");

  return false;
}


// ============================================================
// MQTT RECONNECT
// ============================================================

void reconnectMQTT() {

  while (!client.connected()) {

    Serial.println();
    Serial.println("MQTT is disconnected.");

    if (connectMQTT()) {

      Serial.println("MQTT connection restored.");

    } else {

      Serial.println();
      Serial.println("Retrying MQTT in 5 seconds...");

      delay(5000);
    }
  }
}


// ============================================================
// SENSOR INITIALIZATION
// ============================================================

void initializeSensors() {

  Serial.println();
  Serial.println("========================================");
  Serial.println("SENSOR INITIALIZATION");
  Serial.println("========================================");

  // ---------------- BME280 ----------------

  Serial.println("Initializing BME280...");

  bool bmeStatus = bme.begin(0x77);

  if (bmeStatus) {

    Serial.println("BME280 initialized successfully.");

  } else {

    Serial.println("WARNING: BME280 not detected at address 0x77.");

    Serial.println("Trying address 0x76...");

    bmeStatus = bme.begin(0x76);

    if (bmeStatus) {

      Serial.println("BME280 found at address 0x76.");

    } else {

      Serial.println("ERROR: BME280 not detected.");
    }
  }


  // ---------------- TCS34725 ----------------

  Serial.println();
  Serial.println("Initializing TCS34725...");

  if (tcs.begin()) {

    Serial.println("TCS34725 initialized successfully.");

  } else {

    Serial.println("ERROR: TCS34725 not detected.");
  }


  // ---------------- MQ135 ----------------

  Serial.println();
  Serial.println("Initializing MQ135...");

  Serial.print("MQ135 pin: ");
  Serial.println(MQ135_PIN);

  Serial.println("MQ135 initialized.");
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);

  delay(2000);

  Serial.println();
  Serial.println();
  Serial.println("################################################");
  Serial.println("#              ESP32 STARTING                  #");
  Serial.println("################################################");

  Serial.print("ESP32 Chip Model: ");
  Serial.println(ESP.getChipModel());

  Serial.print("CPU Frequency: ");
  Serial.print(ESP.getCpuFreqMHz());
  Serial.println(" MHz");


  // ==========================================================
  // I2C
  // ==========================================================

  Serial.println();
  Serial.println("Initializing I2C...");

  Wire.begin(
    SDA_PIN,
    SCL_PIN
  );

  Serial.println("I2C initialized.");

  Serial.print("SDA: GPIO ");
  Serial.println(SDA_PIN);

  Serial.print("SCL: GPIO ");
  Serial.println(SCL_PIN);


  // ==========================================================
  // SENSORS
  // ==========================================================

  initializeSensors();


  // ==========================================================
  // WIFI
  // ==========================================================

  setup_wifi();


  // ==========================================================
  // MQTT
  // ==========================================================

  Serial.println();
  Serial.println("Configuring MQTT client...");

  client.setServer(
    mqtt_server,
    mqtt_port
  );

  client.setBufferSize(1024);

  Serial.println("MQTT client configured.");

  connectMQTT();


  // ==========================================================
  // FINISHED
  // ==========================================================

  Serial.println();
  Serial.println("################################################");
  Serial.println("#            ESP32 INITIALIZATION DONE        #");
  Serial.println("################################################");
  Serial.println();
}


// ============================================================
// READ SENSORS
// ============================================================

bool readSensorsAndPublish() {

  Serial.println();
  Serial.println("----------------------------------------");
  Serial.println("READING SENSORS");
  Serial.println("----------------------------------------");


  // ==========================================================
  // BME280
  // ==========================================================

  float temperature = bme.readTemperature();

  float humidity = bme.readHumidity();

  float pressure =
    bme.readPressure() / 100.0F;


  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println(" C");

  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.println(" %");

  Serial.print("Pressure: ");
  Serial.print(pressure);
  Serial.println(" hPa");


  // ==========================================================
  // MQ135
  // ==========================================================

  float mqPPM = mq135.getPPM();

  Serial.print("MQ135 PPM: ");
  Serial.println(mqPPM);


  // ==========================================================
  // CJMCU VOC
  // ==========================================================

  int rawVOC =
    analogRead(CJMCU_PIN);

  float vocVoltage =
    rawVOC * (3.3 / 4095.0);


  Serial.print("VOC raw: ");
  Serial.println(rawVOC);

  Serial.print("VOC voltage: ");
  Serial.print(vocVoltage);
  Serial.println(" V");


  // ==========================================================
  // TCS34725
  // ==========================================================

  uint16_t r, g, b, c;

  tcs.getRawData(
    &r,
    &g,
    &b,
    &c
  );


  Serial.print("Red: ");
  Serial.println(r);

  Serial.print("Green: ");
  Serial.println(g);

  Serial.print("Blue: ");
  Serial.println(b);

  Serial.print("Clear: ");
  Serial.println(c);


  float colorTemp =
    tcs.calculateColorTemperature(
      r,
      g,
      b
    );

  float lux =
    tcs.calculateLux(
      r,
      g,
      b
    );


  Serial.print("Color temperature: ");
  Serial.print(colorTemp);
  Serial.println(" K");

  Serial.print("Lux: ");
  Serial.println(lux);


  // ==========================================================
  // DERIVED VALUES
  // ==========================================================

  float dewPoint =
    temperature -
    ((100 - humidity) / 5.0);


  float absHumidity =
    (
      6.112 *
      exp(
        (17.67 * temperature) /
        (temperature + 243.5)
      ) *
      humidity *
      2.1674
    ) /
    (273.15 + temperature);


  float heatIndex =
    temperature +
    (0.33 * absHumidity) -
    (0.7 * 1) -
    4.0;


  // ==========================================================
  // RATES
  // ==========================================================

  unsigned long currentTime =
    millis();

  float mqRate = 0;

  float vocRate = 0;


  if (prevTime != 0) {

    float dt =
      (currentTime - prevTime) /
      1000.0;

    if (dt > 0) {

      mqRate =
        (mqPPM - prevMQ) / dt;

      vocRate =
        (rawVOC - prevVOC) / dt;
    }
  }


  prevMQ = mqPPM;
  prevVOC = rawVOC;
  prevTime = currentTime;


  // ==========================================================
  // INDEXES
  // ==========================================================

  float moldRisk =
    humidity * 0.6 +
    temperature * 0.4;


  float environmentalStress =
    (temperature * 0.3) +
    (humidity * 0.3) +
    (mqPPM * 0.2) +
    (rawVOC * 0.2);


  float storageSafetyScore =
    100 - environmentalStress;


  if (storageSafetyScore < 0) {
    storageSafetyScore = 0;
  }


  float aromaIndex =
    mqPPM * 0.7 +
    rawVOC * 0.3;


  float colorIndex =
    (r + g + b) / 3.0;


  float oxidationIndex =
    (absHumidity * 0.5) +
    (temperature * 0.5);


  // ==========================================================
  // CREATE JSON
  // ==========================================================

  StaticJsonDocument<1536> doc;

  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["pressure"] = pressure;

  doc["mq135_ppm"] = mqPPM;
  doc["cjmcuvoc_raw"] = rawVOC;
  doc["voc_voltage"] = vocVoltage;

  doc["red"] = r;
  doc["green"] = g;
  doc["blue"] = b;
  doc["clear"] = c;

  doc["color_temp"] = colorTemp;
  doc["lux"] = lux;

  doc["dew_point"] = dewPoint;
  doc["absolute_humidity"] = absHumidity;
  doc["heat_index"] = heatIndex;

  doc["mq_rate"] = mqRate;
  doc["voc_rate"] = vocRate;

  doc["mold_risk"] = moldRisk;
  doc["environmental_stress"] =
    environmentalStress;

  doc["storage_safety_score"] =
    storageSafetyScore;

  doc["aroma_index"] =
    aromaIndex;

  doc["color_index"] =
    colorIndex;

  doc["oxidation_index"] =
    oxidationIndex;


  // ==========================================================
  // SERIALIZE JSON
  // ==========================================================

  char buffer[1536];

  size_t jsonSize =
    serializeJson(
      doc,
      buffer
    );


  Serial.println();
  Serial.println("----------------------------------------");
  Serial.println("JSON DATA");
  Serial.println("----------------------------------------");

  Serial.print("JSON size: ");
  Serial.print(jsonSize);
  Serial.println(" bytes");

  Serial.println(buffer);


  // ==========================================================
  // MQTT PUBLISH
  // ==========================================================

  Serial.println();
  Serial.println("----------------------------------------");
  Serial.println("MQTT PUBLISH");
  Serial.println("----------------------------------------");

  Serial.print("Topic: ");
  Serial.println(mqtt_topic);

  Serial.println("Publishing...");


  bool success =
    client.publish(
      mqtt_topic,
      buffer
    );


  if (success) {

    Serial.println("SUCCESS: MQTT message published.");

  } else {

    Serial.println("ERROR: MQTT publish failed.");

    Serial.print(
      "MQTT state: "
    );

    Serial.println(
      client.state()
    );
  }


  return success;
}


// ============================================================
// MAIN LOOP
// ============================================================

void loop() {

  // ----------------------------------------------------------
  // Check Wi-Fi
  // ----------------------------------------------------------

  if (WiFi.status() != WL_CONNECTED) {

    Serial.println();
    Serial.println("WARNING: Wi-Fi disconnected.");

    setup_wifi();

    delay(1000);
  }


  // ----------------------------------------------------------
  // Check MQTT
  // ----------------------------------------------------------

  if (!client.connected()) {

    reconnectMQTT();
  }


  // IMPORTANT
  // Must be called regularly for PubSubClient
  client.loop();


  // ----------------------------------------------------------
  // Read sensors and publish
  // ----------------------------------------------------------

  readSensorsAndPublish();


  // ----------------------------------------------------------
  // Wait
  // ----------------------------------------------------------

  Serial.println();
  Serial.println("Waiting 10 seconds...");

  for (int i = 0; i < 10; i++) {

    delay(1000);

    // Keep MQTT connection alive
    client.loop();
  }
}