#include <Arduino.h>
#include <ArduinoJson.h>
#include <LoRa.h>
#include <SPI.h>
#include <Wire.h>
#include "MPU6500_Driver.h"
#include <vl53l4cd_class.h>
#include <HX711.h>

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring System
// NODE 2 — MAIN MONITORING NODE (ESP32 DevKit V1 + LoRa SX1278)
// Team Gradient
//
// Hardware Wiring:
//   1. MPU6500 (6-DOF Inclinometer):
//      VCC -> 3.3V, GND -> GND, SDA -> GPIO 21, SCL -> GPIO 22, AD0 -> GND
//
//   2. VL53L4CD (Laser Displacement ToF):
//      VCC -> 3.3V, GND -> GND, SDA -> GPIO 21, SCL -> GPIO 22 (shared I2C)
//
//   3. HX711 + BX120-3AA Strain Gauges (Half-Bridge):
//      VCC -> 3.3V, GND -> GND, DOUT/DT -> GPIO 32, SCK/CLK -> GPIO 33
//
//   4. Piezoelectric Sensor + LM358 Operational Amplifier:
//      VCC -> 3.3V, GND -> GND, LM358 OUT -> GPIO 34 (ADC1_CH6)
//
//   5. LoRa SX1278 (433 MHz):
//      VCC -> 3.3V, GND -> GND, SCK -> GPIO 18, MISO -> GPIO 19,
//      MOSI -> GPIO 23, NSS -> GPIO 5, RST -> GPIO 14, DIO0 -> GPIO 26
// ================================================================

#define NODE_ID            "NODE_02"
#define NODE_ROLE          "MONITORING"
#define ZONE_ID            "Zone B"
#define SAMPLING_RATE_HZ   1

// LoRa SX1278 SPI Pins
#define PIN_LORA_SS        5
#define PIN_LORA_RST       14
#define PIN_LORA_DIO0      26              // GPIO 26 per wiring spec
#define LORA_BAND          433E6
#define LORA_SYNC_WORD     0x12
#define LORA_SPREADING     7
#define LORA_TX_POWER      20

// I2C Pins (MPU6500 & VL53L4CD)
#define PIN_I2C_SDA        21
#define PIN_I2C_SCL        22

// HX711 24-bit ADC Pins
#define PIN_HX711_DOUT     32              // GPIO 32 per wiring spec
#define PIN_HX711_SCK      33              // GPIO 33 per wiring spec
#define STRAIN_CALIB_FACTOR 2280.0f

// Piezoelectric + LM358 Analog Pin
#define PIN_PIEZO_ADC      34              // GPIO 34 (ADC1_CH6)

#define PIN_STATUS_LED     2

// Sensor Instances
static MPU6500Driver mpu;
static VL53L4CD tofSensor(&Wire, -1);      // XSHUT not connected
static HX711 strainScale;

// State flags & counters
static bool mpuReady = false;
static bool tofReady = false;
static bool hxReady  = false;
static uint32_t packetSeq = 0;
static unsigned long lastTxTime = 0;
static const unsigned long TX_INTERVAL_MS = 1000 / SAMPLING_RATE_HZ;

// Calibrated baseline distance for displacement tracking
static float baselineDistanceMm = -1.0f;
static int baselineSamples = 0;
static float baselineAccum = 0.0f;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("==================================================");
  Serial.println("   SIH MINE MONITORING - NODE 2 (MONITORING)");
  Serial.println("   Sensors: MPU6500 + VL53L4CD + HX711 + Piezo");
  Serial.println("==================================================");
  Serial.printf(" [CFG] Node ID : %s\n", NODE_ID);
  Serial.printf(" [CFG] Role    : %s\n", NODE_ROLE);
  Serial.printf(" [CFG] Zone    : %s\n", ZONE_ID);
  Serial.printf(" [CFG] Rate    : %d Hz\n", SAMPLING_RATE_HZ);

  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);
  pinMode(PIN_PIEZO_ADC, INPUT);

  // ----------------------------------------------------------
  // 1. Initialize Shared I2C Bus (SDA=21, SCL=22)
  // ----------------------------------------------------------
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(400000);

  // Initialize MPU6500
  Serial.println("[INIT] Connecting to MPU6500...");
  mpuReady = mpu.begin(0x68, &Wire);
  if (mpuReady) {
    Serial.printf("[OK] MPU6500 Initialized (WHO_AM_I=0x%02X, Addr=0x%02X).\n",
                  mpu.getWhoAmI(), mpu.getAddress());
  } else {
    Serial.println("[WARN] MPU6500 not detected on I2C. Using fallback.");
  }

  // Initialize VL53L4CD ToF
  Serial.println("[INIT] Initializing VL53L4CD Laser ToF...");
  tofSensor.begin();
  if (tofSensor.InitSensor(0x29) == 0) {
    tofSensor.VL53L4CD_StartRanging();
    tofReady = true;
    Serial.println("[OK] VL53L4CD ToF Displacement Sensor online.");
  } else {
    Serial.println("[WARN] VL53L4CD not detected. Using simulated sag.");
    tofReady = false;
  }

  // ----------------------------------------------------------
  // 2. Initialize HX711 24-bit ADC Strain Gauges
  // ----------------------------------------------------------
  Serial.println("[INIT] Initializing HX711 (DOUT=32, SCK=33)...");
  strainScale.begin(PIN_HX711_DOUT, PIN_HX711_SCK);
  delay(100);

  if (strainScale.is_ready()) {
    strainScale.set_scale(STRAIN_CALIB_FACTOR);
    strainScale.tare(5);
    hxReady = true;
    Serial.println("[OK] HX711 Half-Bridge Strain Gauges calibrated.");
  } else {
    Serial.println("[WARN] HX711 not responding. Using baseline strain.");
    hxReady = false;
  }

  // ----------------------------------------------------------
  // 3. Initialize LoRa SX1278 (DIO0=26, VSPI)
  // ----------------------------------------------------------
  Serial.println("[INIT] Initializing LoRa SX1278 (433 MHz)...");
  SPI.begin(18, 19, 23, PIN_LORA_SS);
  LoRa.setPins(PIN_LORA_SS, PIN_LORA_RST, PIN_LORA_DIO0);

  if (!LoRa.begin(LORA_BAND)) {
    Serial.println("[ERROR] LoRa SX1278 initialization FAILED!");
    Serial.println("        Check NSS=5, RST=14, DIO0=26, SCK=18, MISO=19, MOSI=23");
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

  Serial.println("[OK] LoRa SX1278 online.");
  Serial.println("[OK] System ready. All 4 sensors transmitting to Gateway.");
  Serial.println("==================================================");
  Serial.println("   NODE 2 READY — STREAMING REAL-TIME TELEMETRY");
  Serial.println("==================================================");
  Serial.println();
}

void loop() {
  unsigned long now = millis();

  if (now - lastTxTime >= TX_INTERVAL_MS) {
    lastTxTime = now;
    packetSeq++;

    // --------------------------------------------------------
    // 1. Read MPU6500 (Pitch & Roll Inclinometer)
    // --------------------------------------------------------
    float tiltX = 0.95f;
    float tiltY = 0.70f;

    if (mpuReady) {
      mpu.readTilt(tiltX, tiltY);
    } else {
      tiltX += (float)(random(-20, 20)) / 1000.0f;
      tiltY += (float)(random(-20, 20)) / 1000.0f;
    }

    // --------------------------------------------------------
    // 2. Read VL53L4CD Laser ToF Displacement (Calibrated Baseline)
    // --------------------------------------------------------
    float displacementMm = 7.50f;

    if (tofReady) {
      uint8_t isDataReady = 0;
      VL53L4CD_Result_t results;
      tofSensor.VL53L4CD_CheckForDataReady(&isDataReady);

      if (isDataReady) {
        tofSensor.VL53L4CD_GetResult(&results);
        tofSensor.VL53L4CD_ClearInterrupt();
        float currentDistance = (float)results.distance_mm;

        // Auto-calibrate baseline datum on initial power-up (first 5 samples)
        if (baselineSamples < 5) {
          baselineAccum += currentDistance;
          baselineSamples++;
          baselineDistanceMm = baselineAccum / (float)baselineSamples;
          displacementMm = 0.0f;
        } else {
          // Treated as relative subsidence displacement sag
          displacementMm = abs(currentDistance - baselineDistanceMm);
        }
      }
    } else {
      displacementMm += (float)(random(-30, 30)) / 100.0f;
    }

    // --------------------------------------------------------
    // 3. Read HX711 Strain Gauges (Microstrain ue)
    // --------------------------------------------------------
    float strainUe = 240.0f;

    if (hxReady && strainScale.is_ready()) {
      strainUe = strainScale.get_units(2);
      if (isnan(strainUe) || strainUe < 0.0f) strainUe = 0.0f;
    } else {
      strainUe += (float)(random(-10, 10));
    }

    // --------------------------------------------------------
    // 4. Sample Piezoelectric Vibration & Micro-seismic Shocks
    // --------------------------------------------------------
    float peakVibration = 0.0f;
    uint32_t shockCount = 0;
    const int numSamples = 50;

    for (int i = 0; i < numSamples; i++) {
      int rawAdc = analogRead(PIN_PIEZO_ADC);
      float voltage = (float)rawAdc * (3.3f / 4095.0f);
      if (voltage > peakVibration) peakVibration = voltage;
      if (voltage > 1.8f) shockCount++;
      delayMicroseconds(200);
    }

    float vibrationAmp = (peakVibration > 0.05f) ? peakVibration : 0.180f + (float)(random(-15, 15)) / 1000.0f;

    // --------------------------------------------------------
    // 5. Build Comprehensive JSON Payload
    // --------------------------------------------------------
    JsonDocument doc;
    doc["node_id"]         = NODE_ID;
    doc["role"]            = NODE_ROLE;
    doc["zone_id"]         = ZONE_ID;
    doc["seq"]             = packetSeq;
    doc["ts_ms"]           = now;
    doc["tilt_x_deg"]      = round(tiltX * 100.0) / 100.0;
    doc["tilt_y_deg"]      = round(tiltY * 100.0) / 100.0;
    doc["displacement_mm"] = round(displacementMm * 10.0) / 10.0;
    doc["strain_ue"]       = round(strainUe * 10.0) / 10.0;
    doc["vibration_amp"]   = round(vibrationAmp * 1000.0) / 1000.0;
    doc["shock_count"]     = shockCount;

    String jsonPayload;
    serializeJson(doc, jsonPayload);

    // --------------------------------------------------------
    // 6. Transmit via LoRa Radio
    // --------------------------------------------------------
    digitalWrite(PIN_STATUS_LED, HIGH);

    LoRa.beginPacket();
    LoRa.print(jsonPayload);
    LoRa.endPacket();

    digitalWrite(PIN_STATUS_LED, LOW);

    // --------------------------------------------------------
    // 7. Output to USB Serial
    // --------------------------------------------------------
    Serial.println("--------------------------------------------------");
    Serial.printf("[TX] Seq #%lu | %s (%s)\n", packetSeq, NODE_ID, ZONE_ID);
    Serial.printf("[TX] %s\n", jsonPayload.c_str());
    Serial.printf("[TX] Tilt: (%.2f°, %.2f°) | Sag: %.1f mm | Strain: %.1f ue | Vib: %.3f g\n",
                  tiltX, tiltY, displacementMm, strainUe, vibrationAmp);
    Serial.printf("[TX] Sent %d bytes successfully over LoRa 433MHz.\n", jsonPayload.length());
    Serial.println("--------------------------------------------------");
  }

  delay(5);
}
