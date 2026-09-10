#include <Arduino.h>
#include <ArduinoJson.h>
#include <LoRa.h>
#include <SPI.h>
#include <Wire.h>
#include "MPU6500_Driver.h"

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring System
// NODE 1 — REFERENCE NODE (ESP32 DevKit V1 + LoRa SX1278)
// Team Gradient
//
// Hardware Wiring:
//   MPU6500 (ONLY):
//     VCC  -> 3.3V
//     GND  -> GND
//     SDA  -> GPIO 21
//     SCL  -> GPIO 22
//     AD0  -> GND (I2C Address 0x68)
//
//   LoRa SX1278 (433 MHz):
//     VCC  -> 3.3V
//     GND  -> GND
//     SCK  -> GPIO 18
//     MISO -> GPIO 19
//     MOSI -> GPIO 23
//     NSS  -> GPIO 5
//     RST  -> GPIO 14
//     DIO0 -> GPIO 26
//
// Purpose:
//   - Establishes the baseline reference orientation (pitch/roll)
//     of the stable monitoring datum to eliminate false alarms.
// ================================================================

#define NODE_ID          "NODE_A1"       // Reference Node Identifier
#define ZONE_ID          "Zone A"
#define SAMPLING_RATE_HZ 1               // 1 Hz continuous telemetry

// LoRa SX1278 Pin Mapping
#define PIN_LORA_SS      5
#define PIN_LORA_RST     14
#define PIN_LORA_DIO0    26              // GPIO 26 per system wiring spec
#define LORA_BAND        433E6           // 433 MHz ISM band
#define LORA_SYNC_WORD   0x12
#define LORA_SPREADING   7
#define LORA_TX_POWER    20

// I2C Pins for MPU6500
#define PIN_I2C_SDA      21
#define PIN_I2C_SCL      22

// Optional onboard status indicator
// #define PIN_STATUS_LED   2  // Deactivated: No LED or Buzzer pins used

static MPU6500Driver mpu;
static bool mpuOnline = false;
static uint32_t seqCounter = 0;
static unsigned long lastTxTime = 0;
static const unsigned long TX_INTERVAL_MS = 1000 / SAMPLING_RATE_HZ;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("==============================================");
  Serial.println("   SIH MINE MONITORING - NODE 1");
  Serial.println("   Role: Reference Baseline Orientation");
  Serial.println("   Sensor: MPU6500 (ONLY)");
  Serial.println("==============================================");
  Serial.printf(" [INIT] Node ID  : %s\n", NODE_ID);
  Serial.printf(" [INIT] Zone ID  : %s\n", ZONE_ID);
  Serial.printf(" [INIT] Rate     : %d Hz\n", SAMPLING_RATE_HZ);

  // ----------------------------------------------------------
  // 1. Initialize I2C Bus for MPU6500
  // ----------------------------------------------------------
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(100000);

  Serial.println("[INIT] Connecting to MPU6500 (0x68)...");
  mpuOnline = mpu.begin(0x68, &Wire);
  if (mpuOnline) {
    Serial.printf("[MPU6500] Initialized. WHO_AM_I=0x%02X, Addr=0x%02X\n",
                  mpu.getWhoAmI(), mpu.getAddress());
  } else {
    Serial.println("[WARN] MPU6500 not detected on I2C. Using zero-drift baseline.");
  }

  // ----------------------------------------------------------
  // 2. Initialize LoRa SX1278 (DIO0 on GPIO 26)
  // ----------------------------------------------------------
  Serial.println("[INIT] Starting LoRa SX1278...");
  SPI.begin(18, 19, 23, PIN_LORA_SS);
  LoRa.setPins(PIN_LORA_SS, PIN_LORA_RST, PIN_LORA_DIO0);

  if (!LoRa.begin(LORA_BAND)) {
    Serial.println("[ERROR] LoRa SX1278 initialization FAILED!");
    Serial.println("        Check NSS=5, RST=14, DIO0=26, SCK=18, MISO=19, MOSI=23");
    while (true) {
      Serial.println("[ERROR] LoRa hardware not responding. Check wiring (3.3V/GND/SPI)...");
      delay(2000);
    }
  }

  LoRa.setSyncWord(LORA_SYNC_WORD);
  LoRa.setSpreadingFactor(LORA_SPREADING);
  LoRa.setSignalBandwidth(125000);
  LoRa.setCodingRate4(5);
  LoRa.setTxPower(LORA_TX_POWER);
  LoRa.enableCrc();

  Serial.println("[OK] LoRa SX1278 initialized.");
  Serial.println("[OK] Freq=433 MHz | SF7 | BW=125kHz | CR=4/5 | CRC=ON");
  Serial.println("==============================================");
  Serial.println("   NODE 1 READY — TRANSMITTING @ 1 Hz");
  Serial.println("==============================================");
  Serial.println();
}

void loop() {
  unsigned long now = millis();

  // Auto-reconnect MPU if offline
  if (!mpuOnline) {
    static unsigned long lastNode1Reconnect = 0;
    if (now - lastNode1Reconnect >= 2000) {
      lastNode1Reconnect = now;
      mpuOnline = mpu.begin(0x68, &Wire);
      if (mpuOnline) {
        Serial.println("[OK] Node 1 Reference MPU reconnected!");
      }
    }
  }

  if (now - lastTxTime >= TX_INTERVAL_MS) {
    lastTxTime = now;
    seqCounter++;

    // --------------------------------------------------------
    // 1. Read Pitch and Roll from MPU6500
    // --------------------------------------------------------
    float tiltX = 0.0f;
    float tiltY = 0.0f;

    if (mpuOnline) {
      mpu.readTilt(tiltX, tiltY);
    }

    // --------------------------------------------------------
    // 2. Build JSON Payload (Reference Node Spec)
    // --------------------------------------------------------
    JsonDocument doc;
    doc["node_id"]         = NODE_ID;
    doc["role"]            = "REFERENCE";
    doc["zone_id"]         = ZONE_ID;
    doc["seq"]             = seqCounter;
    doc["ts_ms"]           = now;
    doc["tilt_x_deg"]      = round(tiltX * 100.0) / 100.0;
    doc["tilt_y_deg"]      = round(tiltY * 100.0) / 100.0;
    // Node 1 reference datum has no sag/strain/piezo sensors
    doc["displacement_mm"] = 0.0;
    doc["strain_ue"]       = 0.0;
    doc["vibration_amp"]   = 0.000;
    doc["shock_count"]     = 0;

    String jsonPayload;
    serializeJson(doc, jsonPayload);

    // --------------------------------------------------------
    // 3. Transmit over LoRa Radio
    // --------------------------------------------------------
    LoRa.beginPacket();
    LoRa.print(jsonPayload);
    LoRa.endPacket();

    // --------------------------------------------------------
    // 4. Output to USB Serial
    // --------------------------------------------------------
    Serial.println("----------------------------------------------");
    Serial.printf("[TX] Seq #%lu | %s\n", seqCounter, NODE_ID);
    Serial.printf("[TX] %s\n", jsonPayload.c_str());
    Serial.printf("[TX] Tilt X=%.2f° Y=%.2f° | Sent %d bytes OK\n",
                  tiltX, tiltY, jsonPayload.length());
    Serial.println("----------------------------------------------");
  }

  delay(5);
}
