#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <LoRa.h>
#include <SPI.h>
#include <WiFi.h>

#include "gateway_config.h"

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring
// GATEWAY NODE 3 — WiFi-Enabled LoRa Receiver
// Team Gradient
//
// Architecture:
//   Sensor Node (underground) --[LoRa 433MHz]--> Gateway ESP32
//   Gateway ESP32 --[WiFi HTTP POST]--> FastAPI Backend (:8000)
//   FastAPI Backend --[WebSocket]--> React Dashboard
// ================================================================

// ----------------------------------------------------------
// Offline telemetry ring buffer
// Stores packets when WiFi / backend is temporarily down
// ----------------------------------------------------------
struct BufferedPacket {
  String json;
};

BufferedPacket offlineBuffer[OFFLINE_BUFFER_SIZE];
int bufferHead = 0;
int bufferCount = 0;

// Runtime statistics
uint32_t totalPacketsReceived = 0;
uint32_t totalPacketsForwarded = 0;
uint32_t totalPacketsFailed = 0;
bool wifiConnected = false;
bool backendReachable = false;
unsigned long lastBackendAttempt = 0;
const unsigned long BACKEND_RETRY_INTERVAL = 30000;
unsigned long lastWifiRetry = 0;
const unsigned long WIFI_RETRY_INTERVAL = 15000;

// ----------------------------------------------------------
// Two-Node Topology: Node 1 (Reference) & Node 2 (Monitoring)
// Tracks Node 1 baseline datum to calculate differential strata movement for
// Node 2
// ----------------------------------------------------------
float refDisplacementMm = 0.45;
float refTiltX = 0.02;
float refTiltY = -0.01;
float refStrainUe = 92.5;
bool refNodeOnline = false;
unsigned long lastRefPacketTime = 0;

// ----------------------------------------------------------
// Forward declarations
// ----------------------------------------------------------
void connectWiFi();
bool postToBackend(const String &jsonPayload);
void flushOfflineBuffer();
void bufferPacket(const String &jsonPayload);
void printWiFiStatus();

// ----------------------------------------------------------
// LoRa Initialization & Background State
// ----------------------------------------------------------
bool loraOnline = false;
unsigned long lastLoRaRetry = 0;
const unsigned long LORA_RETRY_INTERVAL = 5000;

bool initLoRa() {
  // Hardware reset pulse to ensure clean module startup
  pinMode(PIN_LORA_RST, OUTPUT);
  digitalWrite(PIN_LORA_RST, LOW);
  delay(20);
  digitalWrite(PIN_LORA_RST, HIGH);
  delay(50);

  // ESP32 VSPI: SCK=GPIO18, MISO=GPIO19, MOSI=GPIO23
  SPI.begin(18, 19, 23);
  LoRa.setPins(PIN_LORA_SS, PIN_LORA_RST, PIN_LORA_DIO0);
  LoRa.setSPIFrequency(
      1000000); // 1 MHz SPI clock (reliable over breadboard jumper wires)

  // Direct diagnostic SPI read of REG_VERSION (0x42)
  pinMode(PIN_LORA_SS, OUTPUT);
  digitalWrite(PIN_LORA_SS, LOW);
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  SPI.transfer(0x42 & 0x7F);
  uint8_t chipVersion = SPI.transfer(0x00);
  SPI.endTransaction();
  digitalWrite(PIN_LORA_SS, HIGH);

  Serial.println("[INIT] Starting LoRa SX1278...");
  Serial.printf("[INIT] SPI Read Version Register: 0x%02X (Expected: 0x12)\n",
                chipVersion);

  if (!LoRa.begin(LORA_BAND)) {
    Serial.println(
        "[WARN] LoRa SX1278 initialization failed (will retry in background).");
    if (chipVersion == 0x00) {
      Serial.println("[CAUSE] 0x00: Module has no power (check 3.3V/GND) or "
                     "MOSI/MISO disconnected!");
    } else if (chipVersion == 0xFF) {
      Serial.println("[CAUSE] 0xFF: NSS (GPIO5) / SCK (GPIO18) wire loose, or "
                     "module held in reset!");
    } else {
      Serial.printf(
          "[CAUSE] Unexpected chip ID 0x%02X (not an SX1278, or wrong pins)\n",
          chipVersion);
    }
    return false;
  }

  // LoRa radio config — MUST match sensor node
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

  Serial.println();
  Serial.println("[OK] LoRa SX1278 initialized");
  Serial.println("[OK] Frequency : 433 MHz");
  Serial.println("[OK] Spreading : SF7");
  Serial.println("[OK] Bandwidth : 125 kHz");
  Serial.println("[OK] Coding    : 4/5");
  Serial.println("[OK] CRC       : ON");
  Serial.println("[OK] DIO0      : GPIO26");
  return true;
}

// ================================================================
// SETUP
// ================================================================
void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  delay(1000);

  Serial.println();
  Serial.println("==============================================");
  Serial.println("  SIH MINE MONITORING - GATEWAY (WiFi + LoRa)");
  Serial.println("==============================================");
  Serial.printf("[INIT] Gateway ID : %s\n", GATEWAY_ID);
  Serial.printf("[INIT] Firmware   : %s\n", FIRMWARE_VERSION);

  // Status LED
  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  // ----------------------------------------------------------
  // 1. Initialize LoRa SX1278
  // ----------------------------------------------------------
  loraOnline = initLoRa();
  if (!loraOnline) {
    Serial.println("[WARN] Proceeding to WiFi initialization. LoRa will retry "
                   "in background...");
  }

  // ----------------------------------------------------------
  // 2. Initialize WiFi
  // ----------------------------------------------------------
  connectWiFi();

  // ----------------------------------------------------------
  // 3. Send boot announcement to backend
  // ----------------------------------------------------------
  JsonDocument bootDoc;
  bootDoc["event"] = "GATEWAY_READY";
  bootDoc["gateway_id"] = GATEWAY_ID;
  bootDoc["firmware"] = FIRMWARE_VERSION;
  bootDoc["ip"] = WiFi.localIP().toString();
  bootDoc["rssi_wifi"] = WiFi.RSSI();
  bootDoc["freq_mhz"] = 433.0;
  bootDoc["lora_online"] = loraOnline;
  bootDoc["uptime_ms"] = millis();

  String bootJson;
  serializeJson(bootDoc, bootJson);
  Serial.println(bootJson);
  postToBackend(bootJson);

  Serial.println();
  Serial.println("==============================================");
  Serial.println("  GATEWAY READY — WAITING FOR SENSOR NODES");
  Serial.printf("  Backend: http://%s:%d\n", BACKEND_HOST, BACKEND_PORT);
  Serial.printf("  LoRa Status: %s\n",
                loraOnline ? "ONLINE" : "WAITING FOR MODULE");
  Serial.println("==============================================");
  Serial.println();
}

// ================================================================
// MAIN LOOP
// ================================================================
void loop() {

  // ----------------------------------------------------------
  // Maintain WiFi connection (non-blocking)
  // ----------------------------------------------------------
  if (WiFi.status() != WL_CONNECTED) {
    if (wifiConnected) {
      Serial.println("[WIFI] Connection lost!");
      wifiConnected = false;
    }
    if (millis() - lastWifiRetry >= WIFI_RETRY_INTERVAL) {
      lastWifiRetry = millis();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  } else {
    if (!wifiConnected) {
      wifiConnected = true;
      Serial.println("\n[WIFI] Connected to network!");
      printWiFiStatus();
    }
  }

  // ----------------------------------------------------------
  // Flush any buffered offline packets (only if backend reachable)
  // ----------------------------------------------------------
  if (wifiConnected && backendReachable && bufferCount > 0) {
    flushOfflineBuffer();
  }

  // ----------------------------------------------------------
  // Retry LoRa in background if not yet online
  // ----------------------------------------------------------
  if (!loraOnline && (millis() - lastLoRaRetry >= LORA_RETRY_INTERVAL)) {
    lastLoRaRetry = millis();
    loraOnline = initLoRa();
    if (loraOnline) {
      Serial.println("\n[OK] LoRa SX1278 reconnected and ONLINE!");
    }
  }

  // ----------------------------------------------------------
  // Check for incoming LoRa packet
  // ----------------------------------------------------------
  if (!loraOnline) {
    delay(20);
    return;
  }

  int packetSize = LoRa.parsePacket();

  if (packetSize <= 0) {
    delay(10);
    return;
  }

  // Packet received — blink LED
  digitalWrite(PIN_STATUS_LED, HIGH);
  totalPacketsReceived++;

  Serial.println();
  Serial.println("----------------------------------------------");
  Serial.printf("[RX] PACKET #%lu RECEIVED (%d bytes)\n", totalPacketsReceived,
                packetSize);

  // Read LoRa payload
  String payload = "";
  while (LoRa.available()) {
    payload += (char)LoRa.read();
  }

  // Radio quality metrics
  int rssi = LoRa.packetRssi();
  float snr = LoRa.packetSnr();

  Serial.print("[RX] Payload : ");
  Serial.println(payload);
  Serial.printf("[RX] RSSI    : %d dBm\n", rssi);
  Serial.printf("[RX] SNR     : %.1f dB\n", snr);

  // ----------------------------------------------------------
  // Parse payload — supports both CSV and JSON formats
  // ----------------------------------------------------------
  // CSV format from sensor:
  // NODE1,AX:1.003,AY:0.032,AZ:-0.239,GX:-1.29,GY:5.62,GZ:-0.75 JSON format
  // (future):   {"node_id":"NODE_A1","tilt_x_deg":1.0,...}
  // ----------------------------------------------------------

  JsonDocument doc;
  bool parsed = false;

  // Try JSON first
  DeserializationError jsonErr = deserializeJson(doc, payload);

  if (!jsonErr) {
    // Valid JSON packet
    Serial.println("[OK] Valid JSON packet");
    parsed = true;

  } else if (payload.indexOf(',') > 0 && payload.indexOf(':') > 0) {
    // CSV format: NODE1,AX:1.003,AY:0.032,AZ:-0.239,GX:-1.29,GY:5.62,GZ:-0.75
    Serial.println("[PARSE] CSV format detected — converting to JSON");

    // Extract node ID (first field before comma)
    int firstComma = payload.indexOf(',');
    String nodeId = payload.substring(0, firstComma);
    nodeId.trim();

    // Parse key:value pairs
    float ax = 0, ay = 0, az = 0, gx = 0, gy = 0, gz = 0;
    String remaining = payload.substring(firstComma + 1);

    // Tokenize by comma
    while (remaining.length() > 0) {
      int comma = remaining.indexOf(',');
      String token;
      if (comma >= 0) {
        token = remaining.substring(0, comma);
        remaining = remaining.substring(comma + 1);
      } else {
        token = remaining;
        remaining = "";
      }
      token.trim();

      int colon = token.indexOf(':');
      if (colon < 0)
        continue;

      String key = token.substring(0, colon);
      float val = token.substring(colon + 1).toFloat();

      if (key == "AX")
        ax = val;
      else if (key == "AY")
        ay = val;
      else if (key == "AZ")
        az = val;
      else if (key == "GX")
        gx = val;
      else if (key == "GY")
        gy = val;
      else if (key == "GZ")
        gz = val;
    }

    // Convert raw MPU6500 data to geotechnical telemetry:
    // - tilt_x/y from accelerometer (atan2 in degrees)
    // - vibration from gyroscope RMS
    // - displacement derived from tilt magnitude
    float tiltX = atan2(ay, sqrt(ax * ax + az * az)) * 180.0 / PI;
    float tiltY = atan2(ax, sqrt(ay * ay + az * az)) * 180.0 / PI;
    float vibAmp = sqrt(gx * gx + gy * gy + gz * gz) / 100.0;
    float displacement =
        sqrt(tiltX * tiltX + tiltY * tiltY) * 0.5; // mm estimate
    float strain =
        abs(tiltX) * 50.0 + abs(tiltY) * 30.0; // microstrain estimate

    // Build JSON document from parsed CSV
    bool isRefNode = (nodeId.indexOf("1") >= 0 || nodeId.indexOf("A") >= 0 ||
                      nodeId.indexOf("REF") >= 0);
    doc["node_id"] = isRefNode ? "NODE_01" : "NODE_02";
    doc["role"] = isRefNode ? "REFERENCE" : "MONITORING";
    doc["zone_id"] = isRefNode ? "Zone A" : "Zone B";
    doc["tilt_x_deg"] = round(tiltX * 1000.0) / 1000.0;
    doc["tilt_y_deg"] = round(tiltY * 1000.0) / 1000.0;
    doc["displacement_mm"] = round(displacement * 100.0) / 100.0;
    doc["strain_ue"] = round(strain * 10.0) / 10.0;
    doc["vibration_amp"] = round(vibAmp * 10000.0) / 10000.0;
    doc["shock_count"] = (uint32_t)0;
    doc["seq"] = totalPacketsReceived;

    Serial.printf("[DATA] Node ID       : %s (%s)\n",
                  doc["node_id"].as<const char *>(),
                  doc["role"].as<const char *>());
    Serial.printf("[DATA] Tilt X        : %.3f deg\n", tiltX);
    Serial.printf("[DATA] Tilt Y        : %.3f deg\n", tiltY);
    Serial.printf("[DATA] Displacement  : %.2f mm\n", displacement);
    Serial.printf("[DATA] Strain        : %.1f ue\n", strain);
    Serial.printf("[DATA] Vibration     : %.4f\n", vibAmp);
    Serial.printf("[DATA] Raw AX:%.3f AY:%.3f AZ:%.3f\n", ax, ay, az);
    Serial.printf("[DATA] Raw GX:%.2f GY:%.2f GZ:%.2f\n", gx, gy, gz);

    parsed = true;

  } else {
    Serial.printf("[WARN] Unrecognized format: %s\n", payload.c_str());
    Serial.println("[RAW] Packet received but not forwarded.");
    Serial.println("----------------------------------------------");
    digitalWrite(PIN_STATUS_LED, LOW);
    return;
  }

  // ----------------------------------------------------------
  // Normalize & Process Node Roles (Node 1 Reference vs Node 2 Monitoring)
  // ----------------------------------------------------------
  String rawNodeId = doc["node_id"] | "NODE_02";
  bool isReferenceNode =
      (rawNodeId.indexOf("1") >= 0 || rawNodeId.indexOf("A") >= 0 ||
       rawNodeId.indexOf("REF") >= 0);

  if (isReferenceNode) {
    doc["node_id"] = "NODE_01";
    doc["role"] = "REFERENCE";
    if (!doc["zone_id"].is<const char *>())
      doc["zone_id"] = "Zone A";

    // Update Gateway internal reference baseline
    if (doc["displacement_mm"].is<float>())
      refDisplacementMm = doc["displacement_mm"].as<float>();
    if (doc["tilt_x_deg"].is<float>())
      refTiltX = doc["tilt_x_deg"].as<float>();
    if (doc["tilt_y_deg"].is<float>())
      refTiltY = doc["tilt_y_deg"].as<float>();
    if (doc["strain_ue"].is<float>())
      refStrainUe = doc["strain_ue"].as<float>();
    refNodeOnline = true;
    lastRefPacketTime = millis();

    Serial.printf("[REF_DATUM] Updated Node 1 Baseline: Disp=%.2f mm, "
                  "Tilt=(%.3f°, %.3f°)\n",
                  refDisplacementMm, refTiltX, refTiltY);
  } else {
    // Node 2 is the active monitoring node
    doc["node_id"] = "NODE_02";
    doc["role"] = "MONITORING";
    if (!doc["zone_id"].is<const char *>())
      doc["zone_id"] = "Zone B";

    // Compute differential displacement and tilt against Node 1 reference datum
    float currentDisp = doc["displacement_mm"] | 0.0f;
    float currentTiltX = doc["tilt_x_deg"] | 0.0f;
    float currentTiltY = doc["tilt_y_deg"] | 0.0f;

    float diffDisp = currentDisp - refDisplacementMm;
    float diffTilt =
        sqrt(pow(currentTiltX - refTiltX, 2) + pow(currentTiltY - refTiltY, 2));

    doc["ref_displacement_mm"] = round(refDisplacementMm * 100.0) / 100.0;
    doc["differential_displacement_mm"] = round(diffDisp * 100.0) / 100.0;
    doc["differential_tilt_deg"] = round(diffTilt * 1000.0) / 1000.0;

    Serial.printf(
        "[MONITORING] Node 2 Telemetry (Direct Shared via Gateway):\n");
    Serial.printf("             Raw Sag: %.2f mm | Diff Sag: %.2f mm | Diff "
                  "Tilt: %.3f°\n",
                  currentDisp, diffDisp, diffTilt);
  }

  // ----------------------------------------------------------
  // Enrich packet with gateway metadata
  // ----------------------------------------------------------
  doc["gateway_id"] = GATEWAY_ID;
  doc["rssi_dbm"] = rssi;
  doc["snr_db"] = snr;
  doc["gateway_uptime_ms"] = millis();
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["source"] = "HARDWARE_LORA";

  // Serialize enriched JSON
  String enrichedJson;
  serializeJson(doc, enrichedJson);

  // Output JSON line to USB Serial for direct backend ingestion
  Serial.println(enrichedJson);

  // ----------------------------------------------------------
  // Forward to FastAPI backend via HTTP POST (non-blocking)
  // ----------------------------------------------------------
  if (wifiConnected) {
    if (backendReachable ||
        (millis() - lastBackendAttempt >= BACKEND_RETRY_INTERVAL)) {
      lastBackendAttempt = millis();
      bool success = postToBackend(enrichedJson);

      if (success) {
        backendReachable = true;
        totalPacketsForwarded++;
        Serial.printf("[TX] Forwarded to backend (%lu/%lu total)\n",
                      totalPacketsForwarded, totalPacketsReceived);
      } else {
        backendReachable = false;
        totalPacketsFailed++;
        Serial.println("[TX] Backend HTTP unreachable (backed off 30s) — USB "
                       "Serial active");
      }
    }
  }

  Serial.println("----------------------------------------------");
  digitalWrite(PIN_STATUS_LED, LOW);

  delay(10);
}

// ================================================================
// WiFi Connection Manager
// ================================================================
void connectWiFi() {
  Serial.printf("[WIFI] Initializing WiFi for SSID: \"%s\"...\n", WIFI_SSID);

  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.printf("[WIFI] Connecting to \"%s\"", WIFI_SSID);
  int retries = 0;

  while (WiFi.status() != WL_CONNECTED && retries < WIFI_MAX_RETRIES) {
    delay(WIFI_RETRY_DELAY);
    Serial.print(".");
    retries++;

    // Blink LED while connecting
    digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println(" CONNECTED!");
    printWiFiStatus();
  } else {
    wifiConnected = false;
    Serial.println(" FAILED!");
    Serial.println("[WIFI] Note: ESP32 only supports 2.4 GHz WiFi networks.");
    Serial.println("[WIFI] Will retry in background every 15s. LoRa packets "
                   "will be buffered.");
  }

  digitalWrite(PIN_STATUS_LED, LOW);
}

// ================================================================
// HTTP POST to FastAPI Backend
// ================================================================
bool postToBackend(const String &jsonPayload) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;

  // Build URL: http://192.168.1.100:8000/api/v1/telemetry/ingest
  String url = "http://";
  url += BACKEND_HOST;
  url += ":";
  url += String(BACKEND_PORT);
  url += BACKEND_INGEST_PATH;

  http.begin(url);
  http.setConnectTimeout(800); // Prevent blocking the main loop for 5000ms
  http.setTimeout(800);
  http.addHeader("Content-Type", "application/json");

  int httpCode = http.POST(jsonPayload);

  if (httpCode == 200 || httpCode == 201) {
    String response = http.getString();
    Serial.printf("[HTTP] POST OK (%d) -> %s\n", httpCode, response.c_str());
    http.end();
    return true;
  } else {
    Serial.printf("[HTTP] POST FAILED (code: %d)\n", httpCode);
    if (httpCode > 0) {
      Serial.printf("[HTTP] Response: %s\n", http.getString().c_str());
    }
    http.end();
    return false;
  }
}

// ================================================================
// Offline Ring Buffer — stores packets when backend is unreachable
// ================================================================
void bufferPacket(const String &jsonPayload) {
  if (bufferCount >= OFFLINE_BUFFER_SIZE) {
    // Buffer full — overwrite oldest packet (ring buffer)
    Serial.printf("[BUFFER] Full (%d/%d) — overwriting oldest\n", bufferCount,
                  OFFLINE_BUFFER_SIZE);
  }

  offlineBuffer[bufferHead].json = jsonPayload;
  bufferHead = (bufferHead + 1) % OFFLINE_BUFFER_SIZE;

  if (bufferCount < OFFLINE_BUFFER_SIZE) {
    bufferCount++;
  }

  Serial.printf("[BUFFER] Buffered packet (%d/%d stored)\n", bufferCount,
                OFFLINE_BUFFER_SIZE);
}

void flushOfflineBuffer() {
  Serial.printf("[BUFFER] Flushing %d buffered packets...\n", bufferCount);

  int startIdx =
      (bufferHead - bufferCount + OFFLINE_BUFFER_SIZE) % OFFLINE_BUFFER_SIZE;
  int flushed = 0;

  for (int i = 0; i < bufferCount; i++) {
    int idx = (startIdx + i) % OFFLINE_BUFFER_SIZE;

    if (postToBackend(offlineBuffer[idx].json)) {
      flushed++;
      totalPacketsForwarded++;
    } else {
      // Backend went down again mid-flush — stop and keep remaining
      Serial.printf(
          "[BUFFER] Backend unreachable after flushing %d/%d. Keeping rest.\n",
          flushed, bufferCount);

      // Adjust buffer to only keep unflushed packets
      bufferCount -= flushed;
      return;
    }

    // Small delay between flushes to avoid overwhelming the backend
    delay(50);
  }

  Serial.printf("[BUFFER] All %d packets flushed successfully!\n", flushed);
  bufferCount = 0;
  bufferHead = 0;
}

// ================================================================
// WiFi Status Display
// ================================================================
void printWiFiStatus() {
  Serial.println();
  Serial.println("[WIFI] ---- Connection Info ----");
  Serial.printf("[WIFI] SSID     : %s\n", WiFi.SSID().c_str());
  Serial.printf("[WIFI] IP       : %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("[WIFI] Gateway  : %s\n", WiFi.gatewayIP().toString().c_str());
  Serial.printf("[WIFI] Subnet   : %s\n", WiFi.subnetMask().toString().c_str());
  Serial.printf("[WIFI] DNS      : %s\n", WiFi.dnsIP().toString().c_str());
  Serial.printf("[WIFI] RSSI     : %d dBm\n", WiFi.RSSI());
  Serial.printf("[WIFI] MAC      : %s\n", WiFi.macAddress().c_str());
  Serial.println("[WIFI] ----------------------------");
  Serial.println();
}
