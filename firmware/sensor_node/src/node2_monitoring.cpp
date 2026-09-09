#include <Arduino.h>
#include <ArduinoJson.h>
#include <LoRa.h>
#include <SPI.h>
#include <Wire.h>

#include "config.h"
#include "sensors.h"

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring System
// NODE 2: MAIN MONITORING NODE (ESP32 DevKit V1 + LoRa SX1278)
// Team Gradient
//
// Sensor Hardware Suite:
//   1. MPU6500             : 6-DOF Tilt Inclinometer (I2C: SDA=21, SCL=22)
//   2. VL53L4CD Laser ToF  : Millimeter Roof Sag Displacement (I2C)
//   3. HX711 24-bit ADC    : BX120-3AA Roof Bolt Micro-Strain Gauge (DOUT=19, SCK=18)
//   4. Piezoelectric LM358 : Seismic Vibration Envelope & Rupture Interrupt (ADC=34, INT=35)
//
// Purpose:
//   - Main active underground monitoring node placed in the deformation panel.
//   - Samples all 4 geotechnical sensors at 1 Hz.
//   - Transmits full live telemetry over LoRa 433MHz to Gateway -> Backend -> Dashboard.
// ================================================================

#define NODE_ID_MONITOR   "NODE_02"
#define NODE_ROLE_MONITOR "MONITORING"
#define ZONE_ID_MONITOR   "Zone B"
#define RATE_HZ           1

static uint32_t seqCounter = 0;
static unsigned long lastSampleTime = 0;
static const unsigned long SAMPLE_INTERVAL_MS = 1000 / RATE_HZ;

// Sensor online flags
static bool mpuOk = false;
static bool vl53Ok = false;
static bool hx711Ok = false;
static bool piezoOk = false;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("==================================================");
  Serial.println("   SIH MINE MONITORING - NODE 2 (MAIN MONITORING)");
  Serial.println("   Sensors: MPU6500 + VL53L4CD + HX711 + Piezo");
  Serial.println("==================================================");
  Serial.printf(" [CFG] Node ID : %s\n", NODE_ID_MONITOR);
  Serial.printf(" [CFG] Role    : %s\n", NODE_ROLE_MONITOR);
  Serial.printf(" [CFG] Zone    : %s\n", ZONE_ID_MONITOR);
  Serial.printf(" [CFG] Rate    : %d Hz\n", RATE_HZ);

  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  // ----------------------------------------------------------
  // 1. Initialize I2C Bus for MPU6500 & VL53L4CD
  // ----------------------------------------------------------
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(100000); // 100 kHz Standard Mode (vastly more reliable on breadboard wires)
  delay(100);

  // I2C Hardware Bus Diagnostics Scanner
  Serial.println("[I2C Scan] Scanning I2C bus (SDA=21, SCL=22)...");
  uint8_t devicesFound = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  [I2C Scan] -> Device detected at address 0x%02X", addr);
      if (addr == 0x29) Serial.print(" (VL53L4CD ToF Laser)");
      else if (addr == 0x68) Serial.print(" (MPU6500 Inclinometer - AD0=GND)");
      else if (addr == 0x69) Serial.print(" (MPU6500 Inclinometer - AD0=3V3)");
      Serial.println();
      devicesFound++;
    }
  }
  if (devicesFound == 0) {
    Serial.println("  [I2C Scan] -> WARNING: No devices detected! Check 3.3V/GND and SDA/SCL lines.");
  } else {
    Serial.printf("  [I2C Scan] %d I2C device(s) confirmed on bus.\n", devicesFound);
  }

  // ----------------------------------------------------------
  // 2. Initialize Geotechnical Sub-Sensors
  // ----------------------------------------------------------
  Serial.println("[INIT] Initializing Geotechnical Sensors...");
  mpuOk   = initMPU6500();
  vl53Ok  = initVL53L4CD();
  hx711Ok = initStrainHX711();
  piezoOk = initPiezo();

  Serial.printf(" [SENSORS] MPU6500 Inclinometer   : %s\n", mpuOk   ? "ONLINE" : "OFFLINE (Fallback)");
  Serial.printf(" [SENSORS] VL53L4CD ToF Sag Laser : %s\n", vl53Ok  ? "ONLINE" : "OFFLINE (Fallback)");
  Serial.printf(" [SENSORS] HX711 Strain Gauge     : %s\n", hx711Ok ? "ONLINE" : "OFFLINE (Fallback)");
  Serial.printf(" [SENSORS] Piezo Vibration/Shock  : %s\n", piezoOk ? "ONLINE" : "OFFLINE (Fallback)");

  // ----------------------------------------------------------
  // 3. Initialize LoRa SX1278 SPI Radio
  // ----------------------------------------------------------
  Serial.println("[INIT] Initializing LoRa SX1278 (433 MHz)...");
  SPI.begin(PIN_LORA_SCK, PIN_LORA_MISO, PIN_LORA_MOSI, PIN_LORA_SS);
  LoRa.setPins(PIN_LORA_SS, PIN_LORA_RST, PIN_LORA_DIO0);

  if (!LoRa.begin(LORA_BAND)) {
    Serial.println();
    Serial.println("**************************************************");
    Serial.println("[ERROR] LoRa initialization FAILED! Check wiring.");
    Serial.println("SX1278 Expected Wiring on ESP32 DevKit V1:");
    Serial.printf("  SCK  -> GPIO %d\n", PIN_LORA_SCK);
    Serial.printf("  MISO -> GPIO %d\n", PIN_LORA_MISO);
    Serial.printf("  MOSI -> GPIO %d\n", PIN_LORA_MOSI);
    Serial.printf("  NSS  -> GPIO %d\n", PIN_LORA_SS);
    Serial.printf("  RST  -> GPIO %d\n", PIN_LORA_RST);
    Serial.printf("  DIO0 -> GPIO %d\n", PIN_LORA_DIO0);
    Serial.println("  VCC  -> 3.3V (Do NOT connect to 5V!)");
    Serial.println("  GND  -> ESP32 GND");
    Serial.println("**************************************************");
    while (true) {
      digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
      delay(200);
    }
  }

  LoRa.setSyncWord(LORA_SYNC_WORD);
  LoRa.setSpreadingFactor(LORA_SPREADING_FACTOR);
  LoRa.setSignalBandwidth(125000);
  LoRa.setCodingRate4(5);
  LoRa.setTxPower(LORA_TX_POWER);
  LoRa.enableCrc();

  Serial.println("[OK] LoRa SX1278 ready. Transmitting to Central Gateway.");
  Serial.println("==================================================");
  Serial.println("   NODE 2 READY — STREAMING REAL-TIME TELEMETRY");
  Serial.println("==================================================");
  Serial.println();
}

void loop() {
  unsigned long now = millis();

  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;
    seqCounter++;

    // ----------------------------------------------------------
    // 1. Acquire Telemetry from All 4 Sensors
    // ----------------------------------------------------------
    float tiltX = 0.0f;
    float tiltY = 0.0f;
    float displacementMm = 0.0f;
    float strainUe = 0.0f;
    float vibrationAmp = 0.0f;
    uint32_t shockCount = 0;

    // Read MPU6500 Inclinometer
    if (mpuOk) {
      readMPU6500(tiltX, tiltY);
    }

    // Read VL53L4CD Laser ToF Displacement
    if (vl53Ok) {
      readVL53L4CD(displacementMm);
    }

    // Read HX711 Microstrain
    if (hx711Ok) {
      readStrainHX711(strainUe);
    }

    // Read Piezo Vibration & Shock Interrupt Count
    if (piezoOk) {
      readPiezo(vibrationAmp, shockCount);
    }

    // ----------------------------------------------------------
    // 2. Build JSON Telemetry Payload
    // ----------------------------------------------------------
    JsonDocument doc;
    doc["node_id"]         = NODE_ID_MONITOR;
    doc["role"]            = NODE_ROLE_MONITOR;
    doc["zone_id"]         = ZONE_ID_MONITOR;
    doc["seq"]             = seqCounter;
    doc["ts_ms"]           = now;
    doc["tilt_x_deg"]      = round(tiltX * 1000.0) / 1000.0;
    doc["tilt_y_deg"]      = round(tiltY * 1000.0) / 1000.0;
    doc["displacement_mm"] = round(displacementMm * 100.0) / 100.0;
    doc["strain_ue"]       = round(strainUe * 10.0) / 10.0;
    doc["vibration_amp"]   = round(vibrationAmp * 10000.0) / 10000.0;
    doc["shock_count"]     = shockCount;

    String jsonPayload;
    serializeJson(doc, jsonPayload);

    // ----------------------------------------------------------
    // 3. Transmit via LoRa 433 MHz Radio
    // ----------------------------------------------------------
    digitalWrite(PIN_STATUS_LED, HIGH);

    LoRa.beginPacket();
    LoRa.print(jsonPayload);
    LoRa.endPacket();

    digitalWrite(PIN_STATUS_LED, LOW);

    // ----------------------------------------------------------
    // 4. Output to USB Serial (Debug)
    // ----------------------------------------------------------
    Serial.println("----------------------------------------------");
    Serial.printf("[TX #%lu] %s (%s) -> LoRa 433MHz | %d bytes\n",
                  seqCounter, NODE_ID_MONITOR, NODE_ROLE_MONITOR, jsonPayload.length());
    Serial.printf("[TX] Payload: %s\n", jsonPayload.c_str());
    Serial.printf("[TX] Sag: %.2f mm | Strain: %.1f µε | Tilt: (%.2f°, %.2f°) | Vib: %.4f g\n",
                  displacementMm, strainUe, tiltX, tiltY, vibrationAmp);
    Serial.println("----------------------------------------------");
  }

  delay(5);
}
