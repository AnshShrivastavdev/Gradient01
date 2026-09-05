#include <Arduino.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <math.h>

#include "sensors.h"
#include "config.h"

static Adafruit_MPU6050 mpu;
static bool mpu_ready = false;

bool initMPU6050() {
    if (!mpu.begin(0x68)) {
        // Retry alternative address 0x69
        if (!mpu.begin(0x69)) {
            Serial.println("[MPU6050] Failed to detect sensor on I2C bus.");
            mpu_ready = false;
            return false;
        }
    }
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    mpu_ready = true;
    Serial.println("[MPU6050] Inclinometer & Accelerometer initialized.");
    return true;
}

bool readMPU6050(float &tilt_x, float &tilt_y) {
    if (!mpu_ready) {
        tilt_x = 0.0f;
        tilt_y = 0.0f;
        return false;
    }

    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);

    // Calculate Pitch (Tilt X) and Roll (Tilt Y) angles in degrees from acceleration vectors
    // pitch = atan2(ay, sqrt(ax^2 + az^2)) * (180.0 / PI)
    // roll  = atan2(-ax, az) * (180.0 / PI)
    float ax = a.acceleration.x;
    float ay = a.acceleration.y;
    float az = a.acceleration.z;

    tilt_x = atan2(ay, sqrt(ax * ax + az * az)) * (180.0f / PI);
    tilt_y = atan2(-ax, az) * (180.0f / PI);

    return true;
}
