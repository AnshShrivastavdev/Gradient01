#include <Arduino.h>
#include <ArduinoJson.h>
#include <LoRa.h>
#include <SPI.h>

#include "gateway_config.h"

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring
// GATEWAY NODE 3
// LoRa Receiver
// ================================================================

void setup() {

  Serial.begin(SERIAL_BAUD_RATE);
  delay(1000);

  Serial.println();
  Serial.println("==============================================");
  Serial.println("      SIH MINE MONITORING - GATEWAY");
  Serial.println("==============================================");

  Serial.printf("[INIT] Gateway ID : %s\n", GATEWAY_ID);
  Serial.printf("[INIT] Firmware   : %s\n", FIRMWARE_VERSION);

  // ESP32 VSPI
  // SCK  = GPIO18
  // MISO = GPIO19
  // MOSI = GPIO23
  // NSS  = GPIO5
  SPI.begin(18, 19, 23, PIN_LORA_SS);

  // LoRa pins
  LoRa.setPins(PIN_LORA_SS, PIN_LORA_RST, PIN_LORA_DIO0);

  Serial.println("[INIT] Starting LoRa SX1278...");

  if (!LoRa.begin(LORA_BAND)) {

    Serial.println("[ERROR] LoRa initialization FAILED!");
    Serial.println("[ERROR] Check:");
    Serial.println("        VCC -> 3.3V");
    Serial.println("        GND -> GND");
    Serial.println("        SCK -> GPIO18");
    Serial.println("        MISO -> GPIO19");
    Serial.println("        MOSI -> GPIO23");
    Serial.println("        NSS -> GPIO5");
    Serial.println("        RESET -> GPIO14");
    Serial.println("        DIO0 -> GPIO26");
    Serial.println("        Antenna connected");

    while (true) {
      delay(1000);
    }
  }

  // Same LoRa configuration as Node 1
  LoRa.setSyncWord(LORA_SYNC_WORD);
  LoRa.setSpreadingFactor(LORA_SPREADING_FACTOR);
  LoRa.setSignalBandwidth(LORA_SIGNAL_BANDWIDTH);
  LoRa.setCodingRate4(LORA_CODING_RATE);
  LoRa.setPreambleLength(LORA_PREAMBLE_LENGTH);

  if (LORA_ENABLE_CRC) {
    LoRa.enableCrc();
  } else {
    LoRa.disableCrc();
  }

  // Status LED
  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  Serial.println();
  Serial.println("[OK] LoRa SX1278 initialized");
  Serial.println("[OK] Frequency : 433 MHz");
  Serial.println("[OK] Spreading : SF7");
  Serial.println("[OK] Bandwidth : 125 kHz");
  Serial.println("[OK] Coding    : 4/5");
  Serial.println("[OK] CRC       : ON");
  Serial.println("[OK] DIO0      : GPIO26");

  Serial.println();
  Serial.println("==============================================");
  Serial.println("       GATEWAY READY");
  Serial.println("       WAITING FOR NODE 1...");
  Serial.println("==============================================");
  Serial.println();
}

void loop() {

  int packetSize = LoRa.parsePacket();

  if (packetSize <= 0) {
    return;
  }

  digitalWrite(PIN_STATUS_LED, HIGH);

  Serial.println();
  Serial.println("----------------------------------------------");
  Serial.println("[RX] PACKET RECEIVED");
  Serial.printf("[RX] Size : %d bytes\n", packetSize);

  // Read LoRa packet
  String payload = "";

  while (LoRa.available()) {
    payload += (char)LoRa.read();
  }

  Serial.print("[RX] Payload : ");
  Serial.println(payload);

  // Signal information
  Serial.print("[RX] RSSI : ");
  Serial.print(LoRa.packetRssi());
  Serial.println(" dBm");

  Serial.print("[RX] SNR  : ");
  Serial.print(LoRa.packetSnr());
  Serial.println(" dB");

  // ============================================================
  // JSON VALIDATION
  // ============================================================

  JsonDocument doc;

  DeserializationError error = deserializeJson(doc, payload);

  if (error) {

    Serial.print("[WARN] Invalid JSON: ");
    Serial.println(error.c_str());

    Serial.println("[RAW] Packet received successfully.");

  } else {

    Serial.println("[OK] Valid JSON packet");

    // Node ID
    const char *nodeId = doc["node_id"] | "UNKNOWN";

    Serial.print("[DATA] Node ID       : ");
    Serial.println(nodeId);

    // Zone ID
    const char *zoneId = doc["zone_id"] | "UNKNOWN";

    Serial.print("[DATA] Zone ID       : ");
    Serial.println(zoneId);

    // Sequence
    if (doc["seq"].is<uint32_t>()) {

      Serial.print("[DATA] Sequence      : ");
      Serial.println(doc["seq"].as<uint32_t>());
    }

    // Tilt X
    if (doc["tilt_x_deg"].is<const char *>()) {

      Serial.print("[DATA] Tilt X        : ");
      Serial.println(doc["tilt_x_deg"].as<const char *>());
    }

    // Tilt Y
    if (doc["tilt_y_deg"].is<const char *>()) {

      Serial.print("[DATA] Tilt Y        : ");
      Serial.println(doc["tilt_y_deg"].as<const char *>());
    }

    // Displacement
    if (doc["displacement_mm"].is<const char *>()) {

      Serial.print("[DATA] Displacement  : ");
      Serial.println(doc["displacement_mm"].as<const char *>());
    }

    // Strain
    if (doc["strain_ue"].is<const char *>()) {

      Serial.print("[DATA] Strain        : ");
      Serial.println(doc["strain_ue"].as<const char *>());
    }

    // Vibration
    if (doc["vibration_amp"].is<const char *>()) {

      Serial.print("[DATA] Vibration     : ");
      Serial.println(doc["vibration_amp"].as<const char *>());
    }

    // Shock count
    if (doc["shock_count"].is<uint32_t>()) {

      Serial.print("[DATA] Shock Count   : ");
      Serial.println(doc["shock_count"].as<uint32_t>());
    }

    Serial.println("[OK] Gateway received Node data");
  }

  Serial.println("----------------------------------------------");

  digitalWrite(PIN_STATUS_LED, LOW);

  delay(10);
}