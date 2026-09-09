#include <Arduino.h>
#include <Wire.h>
#include <math.h>

#include "sensors.h"
#include "config.h"
#include "MPU6500_Driver.h"

static MPU6500Driver mpu;
static bool mpu_ready = false;
static unsigned long lastReconnectAttempt = 0;

bool initMPU6500() {
    Serial.println("[MPU6500] Initializing 6-DOF Inclinometer on I2C bus...");
    MPU6500Driver::recoverBus(PIN_I2C_SDA, PIN_I2C_SCL);
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    Wire.setClock(100000);
    delay(50);

    mpu_ready = mpu.begin(0x68, &Wire);
    if (!mpu_ready) {
        Serial.println("[MPU6500] Failed to detect sensor on I2C bus (0x68/0x69). Will auto-retry in background.");
        return false;
    }
    Serial.printf("[MPU6500] Online (WHO_AM_I=0x%02X, Addr=0x%02X).\n",
                  mpu.getWhoAmI(), mpu.getAddress());
    return true;
}

static void checkAutoReconnect() {
    if (!mpu_ready || !mpu.isOnline()) {
        unsigned long now = millis();
        if (now - lastReconnectAttempt > 2000) {
            lastReconnectAttempt = now;
            mpu_ready = mpu.begin(0x68, &Wire);
            if (mpu_ready) {
                Serial.println("[MPU6500] Sensor auto-reconnected successfully!");
            }
        }
    }
}

bool readMPU6500(float &tilt_x, float &tilt_y) {
    checkAutoReconnect();
    if (!mpu_ready) {
        return false;
    }
    return mpu.readTilt(tilt_x, tilt_y);
}

bool readMPU6500Motion(float &tilt_x, float &tilt_y, float &motion_vib) {
    checkAutoReconnect();
    if (!mpu_ready) {
        return false;
    }
    return mpu.readTiltAndMotion(tilt_x, tilt_y, motion_vib);
}
