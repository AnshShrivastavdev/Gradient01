#include <Arduino.h>

#include "sensors.h"
#include "config.h"

static volatile uint32_t isr_shock_count = 0;

// Interrupt Service Routine for micro-seismic shock spike detection
void IRAM_ATTR piezo_shock_isr() {
    isr_shock_count++;
}

bool initPiezo() {
    pinMode(PIN_PIEZO_ANALOG, INPUT);
    pinMode(PIN_PIEZO_INT, INPUT_PULLDOWN);

    // Attach hardware interrupt on rising edge (seismic rupture pulse)
    attachInterrupt(digitalPinToInterrupt(PIN_PIEZO_INT), piezo_shock_isr, RISING);

    Serial.println("[PIEZO] Piezoelectric Vibration & LM358 Circuit initialized.");
    return true;
}

bool readPiezo(float &vibration_amp, uint32_t &shock_count) {
    // Read 12-bit ADC (0 - 4095) corresponding to peak detected analog envelope (0.0 - 3.3V)
    int raw_adc = analogRead(PIN_PIEZO_ANALOG);
    
    // Convert ADC to approximate g-acceleration unit (0.0 to 4.0 g)
    vibration_amp = ((float)raw_adc / 4095.0f) * 3.3f * 1.25f;

    // Snapshot atomic shock counter and reset window
    shock_count = isr_shock_count;
    isr_shock_count = 0;

    return true;
}
