#include <Arduino.h>
#include <Wire.h>
#include <vl53l4cd_class.h>

#include "sensors.h"
#include "config.h"

static VL53L4CD sensor_vl53(&Wire, PIN_VL53_XSHUT);
static bool vl53_ready = false;

bool initVL53L4CD() {
    pinMode(PIN_VL53_XSHUT, OUTPUT);
    digitalWrite(PIN_VL53_XSHUT, HIGH);
    delay(10);

    if (sensor_vl53.begin() != 0) {
        Serial.println("[VL53L4CD] Sensor initialization failed.");
        vl53_ready = false;
        return false;
    }

    sensor_vl53.VL53L4CD_Off();
    sensor_vl53.VL53L4CD_On();
    sensor_vl53.VL53L4CD_SetRangeTiming(50, 0);
    sensor_vl53.VL53L4CD_StartRanging();

    vl53_ready = true;
    Serial.println("[VL53L4CD] ToF Displacement Sensor initialized.");
    return true;
}

bool readVL53L4CD(float &displacement_mm) {
    if (!vl53_ready) {
        displacement_mm = 0.50f;
        return false;
    }

    uint8_t isDataReady = 0;
    VL53L4CD_Result_t results;
    sensor_vl53.VL53L4CD_CheckForDataReady(&isDataReady);

    if (isDataReady) {
        sensor_vl53.VL53L4CD_GetResult(&results);
        sensor_vl53.VL53L4CD_ClearInterrupt();
        displacement_mm = (float)results.distance_mm;
        return true;
    }

    return false;
}
