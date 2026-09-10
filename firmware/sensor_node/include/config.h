#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ==========================================
// Two-Node Topology: Node 1 (Reference) & Node 2 (Monitoring)
// ==========================================
// Select which node is being flashed:
// Set to 1 for Node 1 (Reference Datum in stable zone)
// Set to 2 for Node 2 (Active Monitoring in strata subsidence panel)
#define CURRENT_NODE_NUMBER 2

#if CURRENT_NODE_NUMBER == 1
  #define NODE_ID          "NODE_01"
  #define NODE_ROLE        "REFERENCE"
  #define ZONE_ID          "Zone A"
  #define NODE_DESCRIPTION "Fixed Bedrock Reference Datum"
#elif CURRENT_NODE_NUMBER == 2
  #define NODE_ID          "NODE_02"
  #define NODE_ROLE        "MONITORING"
  #define ZONE_ID          "Zone B"
  #define NODE_DESCRIPTION "Active Strata Subsidence Monitoring"
#else
  #define NODE_ID          "NODE_UNKNOWN"
  #define NODE_ROLE        "GENERIC"
  #define ZONE_ID          "Zone A"
  #define NODE_DESCRIPTION "Generic Sensor Node"
#endif

#define SAMPLING_RATE_HZ   1      // 1 Hz continuous telemetry
// Note: Hardware configuration uses NO LED or Buzzer pins

// ==========================================
// LoRa SX1278 SPI Pinout & Frequency (VSPI)
// ==========================================
#define LORA_BAND 433E6         // 433 MHz ISM Band
#define PIN_LORA_SCK  18        // VSPI SCK
#define PIN_LORA_MISO 19        // VSPI MISO
#define PIN_LORA_MOSI 23        // VSPI MOSI
#define PIN_LORA_SS   5         // VSPI NSS / Chip Select
#define PIN_LORA_RST  14        // Reset
#define PIN_LORA_DIO0 26        // DIO0 Interrupt (moved from GPIO 2 to free Status LED)

#define LORA_SYNC_WORD 0x12
#define LORA_SPREADING_FACTOR 7
#define LORA_TX_POWER 20

// ==========================================
// Sensor Pinouts & I2C Bus
// ==========================================
// I2C Pins (MPU6500 & VL53L4CD ToF)
#define PIN_I2C_SDA 21
#define PIN_I2C_SCL 22

// HX711 24-Bit ADC (BX120-3AA Strain Gauge)
// Dedicated GPIOs (moved from 18/19 to prevent SPI bus collision)
#define PIN_HX711_DOUT 16       // Digital Input (RX2 pin on ESP32 DevKit)
#define PIN_HX711_SCK  17       // Digital Output (TX2 pin on ESP32 DevKit)
#define STRAIN_CALIBRATION_FACTOR 2280.0f // Calibrated for microstrain (ue)

// Piezoelectric Vibration Sensor (LM358 Comparator & Analog Peak Detector)
#define PIN_PIEZO_ANALOG 34     // ADC1 Channel 6 (Analog Envelope)
#define PIN_PIEZO_INT    35     // Digital interrupt pin for high-g shock counts

// VL53L4CD XSHUT Pin (Moved from 23 to avoid SPI MOSI conflict)
#define PIN_VL53_XSHUT 27

#endif // CONFIG_H
