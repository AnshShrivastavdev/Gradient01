#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ==========================================
// Node Configuration & Identity
// ==========================================
#define NODE_ID "NODE_A1"       // Options: NODE_A1 (Zone A), NODE_B1 (Zone B), NODE_C1 (Zone C)
#define ZONE_ID "Zone A"
#define SAMPLING_RATE_HZ 1      // 1 Hz continuous telemetry

// ==========================================
// LoRa SX1278 SPI Pinout & Frequency
// ==========================================
#define LORA_BAND 433E6         // 433 MHz (or 868E6 / 915E6 depending on regional ISM band)
#define PIN_LORA_SS   5
#define PIN_LORA_RST  14
#define PIN_LORA_DIO0 2

#define LORA_SYNC_WORD 0x12
#define LORA_SPREADING_FACTOR 7
#define LORA_TX_POWER 20

// ==========================================
// Sensor Pinouts & I2C Bus
// ==========================================
// I2C Pins (MPU6050 & VL53L4CD ToF)
#define PIN_I2C_SDA 21
#define PIN_I2C_SCL 22

// HX711 24-Bit ADC (BX120-3AA Strain Gauge)
#define PIN_HX711_DOUT 19
#define PIN_HX711_SCK  18
#define STRAIN_CALIBRATION_FACTOR 2280.0f // Calibrated for microstrain (ue)

// Piezoelectric Vibration Sensor (LM358 Comparator & Analog Peak Detector)
#define PIN_PIEZO_ANALOG 34     // ADC1 Channel 6
#define PIN_PIEZO_INT    35     // Digital interrupt pin for high-g shock counts

// VL53L4CD XSHUT Pin (Optional power gating)
#define PIN_VL53_XSHUT 23

#endif // CONFIG_H
