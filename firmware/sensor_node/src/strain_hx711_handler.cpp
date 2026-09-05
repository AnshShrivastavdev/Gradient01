#include <Arduino.h>
#include <HX711.h>

#include "sensors.h"
#include "config.h"

static HX711 scale;
static bool hx711_ready = false;

bool initStrainHX711() {
    scale.begin(PIN_HX711_DOUT, PIN_HX711_SCK);
    delay(100);

    if (scale.is_ready()) {
        scale.set_scale(STRAIN_CALIBRATION_FACTOR);
        scale.tare(); // Zero out baseline initial load
        hx711_ready = true;
        Serial.println("[HX711] 24-Bit ADC Strain Gauge initialized & tared.");
        return true;
    } else {
        Serial.println("[HX711] Waiting for ADC chip ready...");
        hx711_ready = false;
        return false;
    }
}

bool readStrainHX711(float &strain_ue) {
    if (!hx711_ready) {
        if (scale.is_ready()) {
            scale.set_scale(STRAIN_CALIBRATION_FACTOR);
            hx711_ready = true;
        } else {
            strain_ue = 85.0f;
            return false;
        }
    }

    if (scale.is_ready()) {
        // Reads calibrated microstrain (ue)
        strain_ue = (float)scale.get_units(3);
        if (strain_ue < 0) strain_ue = 0.0f;
        return true;
    }

    return false;
}
