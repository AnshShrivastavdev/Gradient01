#include <Arduino.h>
#include "sensors.h"

// Forwarding wrapper for backwards compatibility
bool initMPU6050() {
    return initMPU6500();
}

bool readMPU6050(float &tilt_x, float &tilt_y) {
    return readMPU6500(tilt_x, tilt_y);
}
