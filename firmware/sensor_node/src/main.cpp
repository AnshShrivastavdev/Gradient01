#include <Arduino.h>
#include <ArduinoJson.h>
#include <LoRa.h>
#include <SPI.h>

#include "gateway_config.h"

// ================================================================
// Gateway Node 3 - LoRa Receiver
// Team Gradient - SIH Underground Coal Mine Monitoring
// ================================================================

// Actual Gateway wiring:
// LoRa DIO0 -> ESP32 GPIO26

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  delay(1000);

  Serial.println();
  Serial.println("==============================================");
  Serial.println("   SIH MINE MONITORING - GATEWAY NODE 3");
  Serial.println("==============================================");

  Serial.printf("[INIT] Gateway ID: %s\n", GATEWAY_ID);
  Serial.printf("[INIT] Firmware: %s\n", FIRMWARE_VERSION);

  // ------------------------------------------------------------
  // Initialize SPI
  // ESP32 DevKit V1
  // SCK  = GPIO18
  // MISO = GPIO19
  // MOSI = GPIO23
  // NSS  = GPIO5
  // ------------------------------------------------------------
  SPI.begin(18, 19, 23, PIN_LORA_SS);

  // ------------------------------------------------------------
  // Initialize LoRa SX1278
  // ------------------------------------------------------------
  LoRa.setPins(PIN_LORA_SS, PIN_LORA_RST, PIN_LORA_DIO0);

  Serial.println("[INIT] Starting LoRa SX1278...");

  if (!LoRa.begin(LORA_BAND)) {
    Serial.println("[ERROR] LoRa initialization FAILED!");
    Serial.println("[ERROR] Check VCC, GND, SPI wiring and antenna.");

    while (true) {
      delay(1000);
    }
  }

  // ------------------------------------------------------------
  // LoRa configuration
  // MUST MATCH NODE 1
  // ------------------------------------------------------------
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

  // ------------------------------------------------------------
  // Status LED
  // ------------------------------------------------------------
  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  Serial.println("[OK] LoRa SX1278 initialized!");
  Serial.println("[OK] Frequency : 433 MHz");
  Serial.println("[OK] Spreading : SF7");
  Serial.println("[OK] Bandwidth : 125 kHz");
  Serial.println("[OK] Coding    : 4/5");
  Serial.println("[OK] CRC       : ON");
  Serial.println("[OK] DIO0      : GPIO26");

  Serial.println();
  Serial.println("==============================================");
  Serial.println("   GATEWAY READY - WAITING FOR NODE 1");
  Serial.println("==============================================");
  Serial.println();
}

void loop() {

  // ------------------------------------------------------------
  // Check for incoming LoRa packet
  // ------------------------------------------------------------
  int packetSize = LoRa.parsePacket();

  if (packetSize) {

    digitalWrite(PIN_STATUS_LED, HIGH);

    Serial.println();
    Serial.println("----------------------------------------------");
    Serial.println("[RX] PACKET RECEIVED");
    Serial.printf("[RX] Packet Size: %d bytes\n", packetSize);

    // --------------------------------------------------------
    // Read complete packet
    // --------------------------------------------------------
    String payload = "";

    while (LoRa.available()) {
      payload += (char)LoRa.read();
    }

    Serial.print("[RX] Payload: ");
    Serial.println(payload);

    // --------------------------------------------------------
    // Radio information
    // --------------------------------------------------------
    Serial.print("[RX] RSSI: ");
    Serial.print(LoRa.packetRssi());
    Serial.println(" dBm");

    Serial.print("[RX] SNR : ");
    Serial.print(LoRa.packetSnr());
    Serial.println(" dB");

    // --------------------------------------------------------
    // Try to parse JSON
    // --------------------------------------------------------
    StaticJsonDocument<512> doc;

    DeserializationError error = deserializeJson(doc, payload);

    if (!error) {

      Serial.println("[OK] Valid JSON packet");

      const char *nodeId = doc["node_id"] | "UNKNOWN";
      const char *zoneId = doc["zone_id"] | "UNKNOWN";

      Serial.print("[DATA] Node ID       : ");
      Serial.println(nodeId);

      Serial.print("[DATA] Zone ID       : ");
      Serial.println(zoneId);

      if (doc.containsKey("seq")) {
        Serial.print("[DATA] Sequence      : ");
        Serial.println(doc["seq"].as<uint32_t>());
      }

      if (doc.containsKey("tilt_x_deg")) {
        Serial.print("[DATA] Tilt X        : ");
        Serial.println(doc["tilt_x_deg"].as<const char *>());
      }

      if (doc.containsKey("tilt_y_deg")) {
        Serial.print("[DATA] Tilt Y        : ");
        Serial.println(doc["tilt_y_deg"].as<const char *>());
      }

      if (doc.containsKey("displacement_mm")) {
        Serial.print("[DATA] Displacement  : ");
        Serial.println(doc["displacement_mm"].as<const char *>());
      }

      if (doc.containsKey("strain_ue")) {
        Serial.print("[DATA] Strain        : ");
        Serial.println(doc["strain_ue"].as<const char *>());
      }

      if (doc.containsKey("vibration_amp")) {
        Serial.print("[DATA] Vibration     : ");
        Serial.println(doc["vibration_amp"].as<const char *>());
      }

      if (doc.containsKey("shock_count")) {
        Serial.print("[DATA] Shock Count   : ");
        Serial.println(doc["shock_count"].as<uint32_t>());
      }

    } else {

      Serial.print("[WARN] Invalid JSON: ");
      Serial.println(error.c_str());

      // Still show raw packet so debugging is easy.
      Serial.println("[RAW] Packet received successfully.");
    }

    Serial.println("----------------------------------------------");

    digitalWrite(PIN_STATUS_LED, LOW);
  }
}