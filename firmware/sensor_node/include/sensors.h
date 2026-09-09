#ifndef SENSORS_H
#define SENSORS_H

#include <Arduino.h>

struct SensorPacket {
    char node_id[16];
    char zone_id[16];
    unsigned long timestamp_ms;
    float tilt_x_deg;
    float tilt_y_deg;
    float displacement_mm;
    float strain_ue;
    float vibration_amp;
    uint32_t shock_count;
};

// Function prototypes for sensor sub-handlers
bool initMPU6500();
bool readMPU6500(float &tilt_x, float &tilt_y);

bool initVL53L4CD();
bool readVL53L4CD(float &displacement_mm);

bool initStrainHX711();
bool readStrainHX711(float &strain_ue);

bool initPiezo();
bool readPiezo(float &vibration_amp, uint32_t &shock_count);

#endif // SENSORS_H
