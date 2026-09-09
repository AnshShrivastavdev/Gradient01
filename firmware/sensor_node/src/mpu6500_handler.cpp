#include <Arduino.h>
#include <Wire.h>
#include <math.h>

#include "sensors.h"
#include "config.h"
#include "MPU6500_Driver.h"

static MPU6500Driver mpu;
static bool mpu_ready = false;

bool initMPU6500() {
    Serial.println("[MPU6500] Initializing 6-DOF Inclinometer on I2C bus...");
    mpu_ready = mpu.begin(0x68, &Wire);
    if (!mpu_ready) {
        Serial.println("[MPU6500] Failed to detect sensor on I2C bus (0x68/0x69).");
        return false;
    }
    Serial.printf("[MPU6500] Online (WHO_AM_I=0x%02X, Addr=0x%02X).\n",
                  mpu.getWhoAmI(), mpu.getAddress());
    return true;
}

bool readMPU6500(float &tilt_x, float &tilt_y) {
    if (!mpu_ready) {
        tilt_x = 0.0f;
        tilt_y = 0.0f;
        return false;
    }

    return mpu.readTilt(tilt_x, tilt_y);
}
