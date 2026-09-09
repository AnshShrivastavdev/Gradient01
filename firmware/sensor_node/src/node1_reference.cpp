#include <Arduino.h>
#include <ArduinoJson.h>
#include <LoRa.h>
#include <SPI.h>
#include <Wire.h>
#include "MPU6500_Driver.h"

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring System
// NODE 1: REFERENCE DATUM NODE (ESP32 DevKit V1 + LoRa SX1278)
// Team Gradient
//
// Sensor Hardware:
//   - ONLY MPU6500 6-DOF Inclinometer (I2C: SDA=21, SCL=22)
//
// Purpose:
//   - Establishes the fixed baseline reference orientation (pitch/roll)
//     of the stable bedrock datum to reduce false alarms.
//   - Does NOT require displacement, strain, or vibration sensors.
//   - Telemetry is transmitted over LoRa 433MHz to Gateway & Backend.
// ================================================================

#define NODE_ID          "NODE_A1"       // Node 1 Reference Identifier
#define NODE_ROLE        "REFERENCE"
#define ZONE_ID          "Zone A"
#define SAMPLING_RATE_HZ 1               // 1 Hz transmission interval

// LoRa SX1278 Radio Pinout (ESP32 VSPI)
#define PIN_LORA_SS      5
#define PIN_LORA_RST     14
#define PIN_LORA_DIO0    26
#define LORA_BAND        433E6           // 433 MHz ISM Band
#define LORA_SYNC_WORD   0x12
#define LORA_SPREADING   7
#define LORA_TX_POWER    20

// I2C Pins for MPU6500
#define PIN_I2C_SDA      21
#define PIN_I2C_SCL      22

// Status LED (GPIO 2 on ESP32 DevKit V1)
#define PIN_STATUS_LED   2

// Runtime state
static MPU6500Driver mpu;
static bool mpuOnline = false;
static uint32_t packetSeq = 0;
static unsigned long lastTxTime = 0;
static const unsigned long TX_INTERVAL_MS = 1000 / SAMPLING_RATE_HZ;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("==============================================");
  Serial.println("   SIH MINE MONITORING - NODE 1 (REFERENCE)");
  Serial.println("   Sensor: MPU6500 Orientation Baseline");
  Serial.println("==============================================");
  Serial.printf(" [CFG] Node ID : %s\n", NODE_ID);
  Serial.printf(" [CFG] Role    : %s\n", NODE_ROLE);
  Serial.printf(" [CFG] Zone    : %s\n", ZONE_ID);
  Serial.printf(" [CFG] Rate    : %d Hz\n", SAMPLING_RATE_HZ);

  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  // ----------------------------------------------------------
  // 1. Initialize I2C Bus and MPU6500
  // ----------------------------------------------------------
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(100000);

  Serial.println("[INIT] Connecting to MPU6500...");
  mpuOnline = mpu.begin(0x68, &Wire);
  if (mpuOnline) {
    Serial.printf("[OK] MPU6500 Initialized (WHO_AM_I=0x%02X, Addr=0x%02X).\n",
                  mpu.getWhoAmI(), mpu.getAddress());
  } else {
    Serial.println("[WARN] MPU6500 not detected on I2C (0x68/0x69). Using fallback baseline.");
  }

  // ----------------------------------------------------------
  // 2. Initialize LoRa SX1278 Transmitter
  // ----------------------------------------------------------
  Serial.println("[INIT] Initializing LoRa SX1278 (433 MHz)...");
  SPI.begin(18, 19, 23, PIN_LORA_SS);
  LoRa.setPins(PIN_LORA_SS, PIN_LORA_RST, PIN_LORA_DIO0);

  if (!LoRa.begin(LORA_BAND)) {
    Serial.println("[ERROR] LoRa SX1278 initialization FAILED!");
    while (true) {
      digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
      delay(200);
    }
  }

  LoRa.setSyncWord(LORA_SYNC_WORD);
  LoRa.setSpreadingFactor(LORA_SPREADING);
  LoRa.setSignalBandwidth(125000);
  LoRa.setCodingRate4(5);
  LoRa.setTxPower(LORA_TX_POWER);
  LoRa.enableCrc();

  Serial.println("[OK] LoRa SX1278 ready.");
  Serial.println("==============================================");
  Serial.println("   NODE 1 READY — TRANSMITTING REFERENCE DATUM");
  Serial.println("==============================================");
  Serial.println();
}

void loop() {
  unsigned long now = millis();

  // Auto-reconnect MPU if offline
  if (!mpuOnline) {
    static unsigned long lastNode1RefReconnect = 0;
    if (now - lastNode1RefReconnect >= 2000) {
      lastNode1RefReconnect = now;
      mpuOnline = mpu.begin(0x68, &Wire);
      if (mpuOnline) {
        Serial.println("[OK] Node 1 Reference MPU reconnected!");
      }
    }
  }

  if (now - lastTxTime >= TX_INTERVAL_MS) {
    lastTxTime = now;
    packetSeq++;

    // --------------------------------------------------------
    // 1. Read Pitch and Roll Tilt from MPU6500
    // --------------------------------------------------------
    float tiltX = 0.0f;
    float tiltY = 0.0f;

    if (mpuOnline) {
      mpu.readTilt(tiltX, tiltY);
    }

    // --------------------------------------------------------
    // 2. Format JSON Telemetry (Reference Format)
    // --------------------------------------------------------
    JsonDocument doc;
    doc["node_id"]         = NODE_ID;
    doc["role"]            = NODE_ROLE;
    doc["zone_id"]         = ZONE_ID;
    doc["seq"]             = packetSeq;
    doc["ts_ms"]           = now;
    doc["tilt_x_deg"]      = round(tiltX * 100.0) / 100.0;
    doc["tilt_y_deg"]      = round(tiltY * 100.0) / 100.0;
    // Node 1 has no displacement/strain/piezo sensors
    doc["displacement_mm"] = 0.0;
    doc["strain_ue"]       = 0.0;
    doc["vibration_amp"]   = 0.000;
    doc["shock_count"]     = 0;

    String jsonPayload;
    serializeJson(doc, jsonPayload);

    // --------------------------------------------------------
    // 3. Transmit via LoRa Radio
    // --------------------------------------------------------
    digitalWrite(PIN_STATUS_LED, HIGH);

    LoRa.beginPacket();
    LoRa.print(jsonPayload);
    LoRa.endPacket();

    digitalWrite(PIN_STATUS_LED, LOW);

    // --------------------------------------------------------
    // 4. Output to USB Serial (Matches live hardware log format)
    // --------------------------------------------------------
    Serial.println("----------------------------------------------");
    Serial.printf("[TX] Seq #%lu | %s\n", packetSeq, NODE_ID);
    Serial.printf("[TX] %s\n", jsonPayload.c_str());
    Serial.printf("[TX] Tilt X=%.2f° Y=%.2f° | Sent %d bytes OK\n",
                  tiltX, tiltY, jsonPayload.length());
    Serial.println("----------------------------------------------");
  }

  delay(5);
}
