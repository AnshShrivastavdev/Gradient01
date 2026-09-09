#ifndef GATEWAY_CONFIG_H
#define GATEWAY_CONFIG_H

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring
// GATEWAY NODE 3 - Configuration Header
// Team Gradient
// ================================================================

// ----------------------------------------------------------
// WiFi Configuration
// CHANGE THESE to your network credentials before flashing!
// ----------------------------------------------------------
#define WIFI_SSID          "CJP"
#define WIFI_PASSWORD      "yuvrajsingh"

// Maximum WiFi connection attempts before reboot
#define WIFI_MAX_RETRIES   30
// Delay between WiFi retry attempts (ms)
#define WIFI_RETRY_DELAY   500

// ----------------------------------------------------------
// FastAPI Backend Endpoint
// The gateway POSTs JSON telemetry here over HTTP.
// Change the IP to your laptop/server running the backend.
// ----------------------------------------------------------
#define BACKEND_HOST       "10.58.28.224"
#define BACKEND_PORT       8000
#define BACKEND_INGEST_PATH "/api/v1/telemetry/ingest"

// Full URL constructed at compile time
#define BACKEND_INGEST_URL "http://" BACKEND_HOST ":" "8000" BACKEND_INGEST_PATH

// HTTP request timeout (ms)
#define HTTP_TIMEOUT_MS    1000

// ----------------------------------------------------------
// Gateway Identity
// ----------------------------------------------------------
#define GATEWAY_ID         "GATEWAY_SURFACE_01"
#define FIRMWARE_VERSION   "3.0.0-WIFI"

// ----------------------------------------------------------
// Serial / UART
// ----------------------------------------------------------
#define SERIAL_BAUD_RATE   115200

// ----------------------------------------------------------
// LoRa SX1278 Pin Mapping (ESP32 DevKit V1)
// ----------------------------------------------------------
//   SX1278 Pin  ->  ESP32 GPIO
//   VCC         ->  3.3V
//   GND         ->  GND
//   SCK         ->  GPIO18
//   MISO        ->  GPIO19
//   MOSI        ->  GPIO23
//   NSS  (CS)   ->  GPIO5
//   RESET       ->  GPIO14
//   DIO0        ->  GPIO26
// ----------------------------------------------------------
#define PIN_LORA_SS        5
#define PIN_LORA_RST       14
#define PIN_LORA_DIO0      26

// ----------------------------------------------------------
// LoRa Radio Configuration
// MUST MATCH sensor node settings exactly!
// ----------------------------------------------------------
#define LORA_BAND              433E6       // 433 MHz ISM band
#define LORA_SYNC_WORD         0x12
#define LORA_SPREADING_FACTOR  7
#define LORA_SIGNAL_BANDWIDTH  125000      // 125 kHz
#define LORA_CODING_RATE       5           // 4/5
#define LORA_PREAMBLE_LENGTH   8
#define LORA_ENABLE_CRC        true

// ----------------------------------------------------------
// Status LED
// ----------------------------------------------------------
#define PIN_STATUS_LED     2               // Built-in LED on most ESP32 DevKit boards

// ----------------------------------------------------------
// Telemetry Buffering (offline resilience)
// ----------------------------------------------------------
// Max packets to buffer when WiFi/backend is temporarily down
#define OFFLINE_BUFFER_SIZE  50

#endif // GATEWAY_CONFIG_H