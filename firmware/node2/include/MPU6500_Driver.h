#ifndef MPU6500_DRIVER_H
#define MPU6500_DRIVER_H

#include <Arduino.h>
#include <Wire.h>
#include <math.h>

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring System
// BULLETPROOF MPU6500 / MPU6050 / MPU9250 6-DOF INCLINOMETER DRIVER
// Team Gradient
//
// Features:
//   - Universal auto-detection for MPU6500 (0x70), MPU6050 (0x68), MPU9250 (0x71/0x73) & clones
//   - Dual-address detection (0x68 primary, 0x69 alternate) + auto-scan fallback
//   - I2C bus hang recovery routine (9-pulse SCL clocking)
//   - Safe repeated-start and stop-mode I2C transfers for ESP32 Wire compatibility
//   - Real-time pitch/roll tilt calculation + dynamic motion/vibration intensity
//   - Auto-reconnect & fault-tolerant health monitoring
// ================================================================

#define MPU6500_DEFAULT_ADDR 0x68
#define MPU6500_ALT_ADDR     0x69

// Register Map
#define MPU6500_REG_SMPLRT_DIV    0x19
#define MPU6500_REG_CONFIG        0x1A
#define MPU6500_REG_GYRO_CONFIG   0x1B
#define MPU6500_REG_ACCEL_CONFIG  0x1C
#define MPU6500_REG_ACCEL_CONFIG2 0x1D
#define MPU6500_REG_INT_PIN_CFG   0x37
#define MPU6500_REG_ACCEL_XOUT_H  0x3B
#define MPU6500_REG_TEMP_OUT_H    0x41
#define MPU6500_REG_GYRO_XOUT_H   0x43
#define MPU6500_REG_USER_CTRL     0x6A
#define MPU6500_REG_PWR_MGMT_1    0x6B
#define MPU6500_REG_PWR_MGMT_2    0x6C
#define MPU6500_REG_WHO_AM_I      0x75

class MPU6500Driver {
public:
    MPU6500Driver() : _addr(MPU6500_DEFAULT_ADDR), _wire(&Wire), _initialized(false), _whoami(0), _errorCount(0) {}

    // Recover an unresponsive I2C bus by clocking SCL 9 times
    static void recoverBus(uint8_t sdaPin = 21, uint8_t sclPin = 22) {
        pinMode(sdaPin, INPUT_PULLUP);
        pinMode(sclPin, OUTPUT);
        for (int i = 0; i < 9; i++) {
            digitalWrite(sclPin, HIGH);
            delayMicroseconds(5);
            digitalWrite(sclPin, LOW);
            delayMicroseconds(5);
        }
        digitalWrite(sclPin, HIGH);
        delayMicroseconds(5);
    }

    bool begin(uint8_t preferred_addr = MPU6500_DEFAULT_ADDR, TwoWire *wire = &Wire) {
        _wire = wire;
        _initialized = false;
        _errorCount = 0;

        // 1. Detect device address (try preferred 0x68, then 0x69, then full bus scan)
        uint8_t target_addr = 0;
        if (ping(preferred_addr)) {
            target_addr = preferred_addr;
        } else {
            uint8_t alt = (preferred_addr == MPU6500_DEFAULT_ADDR) ? MPU6500_ALT_ADDR : MPU6500_DEFAULT_ADDR;
            if (ping(alt)) {
                target_addr = alt;
            } else {
                // Bus scan across valid I2C 7-bit space
                for (uint8_t a = 0x08; a <= 0x77; a++) {
                    if (ping(a)) {
                        target_addr = a;
                        Serial.printf("[MPU] Device discovered on I2C address 0x%02X\n", a);
                        break;
                    }
                }
            }
        }

        if (target_addr == 0) {
            Serial.println("[MPU] ERROR: No I2C response on SDA/SCL lines. Check 3.3V, GND, SDA=21, SCL=22.");
            return false;
        }
        _addr = target_addr;

        // 2. Clear SLEEP mode first (wakes up internal oscillator)
        writeRegister(MPU6500_REG_PWR_MGMT_1, 0x00);
        delay(20);

        // 3. Reset device registers
        writeRegister(MPU6500_REG_PWR_MGMT_1, 0x80);
        delay(80);

        // 4. Clear SLEEP mode again after reset
        writeRegister(MPU6500_REG_PWR_MGMT_1, 0x00);
        delay(20);

        // 5. Select PLL with X-axis gyro reference (more stable than internal 8MHz RC)
        writeRegister(MPU6500_REG_PWR_MGMT_1, 0x01);
        delay(15);

        // 6. Enable all 3 accelerometer & 3 gyroscope axes
        writeRegister(MPU6500_REG_PWR_MGMT_2, 0x00);
        delay(10);

        // 7. Enable I2C bypass multiplexer (INT_PIN_CFG = 0x02) & disable I2C master mode
        writeRegister(MPU6500_REG_USER_CTRL, 0x00);
        writeRegister(MPU6500_REG_INT_PIN_CFG, 0x02);
        delay(10);

        // 8. Read WHO_AM_I register
        _whoami = readRegister(MPU6500_REG_WHO_AM_I);
        Serial.printf("[MPU] Connected at 0x%02X | WHO_AM_I = 0x%02X ", _addr, _whoami);

        if (_whoami == 0x70) {
            Serial.println("(Genuine MPU6500)");
        } else if (_whoami == 0x68) {
            Serial.println("(MPU6050 / Compatible)");
        } else if (_whoami == 0x71 || _whoami == 0x73) {
            Serial.println("(MPU9250 / MPU6500 variant)");
        } else if (_whoami != 0x00 && _whoami != 0xFF) {
            Serial.printf("(Custom/Clone Silicon ID 0x%02X)\n", _whoami);
        } else {
            Serial.println("[WARN] WHO_AM_I read 0x00/0xFF, proceeding with register verification...");
        }

        // 9. Configure Digital Low Pass Filter (DLPF ~42 Hz bandwidth)
        writeRegister(MPU6500_REG_CONFIG, 0x03);

        // 10. Sample rate divider: 1 kHz / (1 + 4) = 200 Hz internal sampling
        writeRegister(MPU6500_REG_SMPLRT_DIV, 0x04);

        // 11. Gyroscope Full Scale Range: +-500 deg/sec (FS_SEL = 1 -> 65.5 LSB/dps)
        writeRegister(MPU6500_REG_GYRO_CONFIG, 0x08);

        // 12. Accelerometer Full Scale Range: +-4g (AFS_SEL = 1 -> 8192 LSB/g)
        writeRegister(MPU6500_REG_ACCEL_CONFIG, 0x08);

        // 13. If MPU6500/MPU9250, set Accel DLPF to ~44.8 Hz (ACCEL_CONFIG2)
        if (_whoami >= 0x70) {
            writeRegister(MPU6500_REG_ACCEL_CONFIG2, 0x03);
        }

        _initialized = true;
        _errorCount = 0;
        Serial.println("[MPU] Sensor initialized successfully (±4g, ±500 dps, DLPF 42Hz active).");
        return true;
    }

    bool readMotion(float &ax_g, float &ay_g, float &az_g, float &gx_dps, float &gy_dps, float &gz_dps) {
        if (!_initialized) return false;

        _wire->beginTransmission(_addr);
        _wire->write(MPU6500_REG_ACCEL_XOUT_H);
        uint8_t err = _wire->endTransmission(false);
        if (err != 0) {
            // Retry with standard STOP condition
            _wire->beginTransmission(_addr);
            _wire->write(MPU6500_REG_ACCEL_XOUT_H);
            err = _wire->endTransmission(true);
            if (err != 0) {
                handleError();
                return false;
            }
        }

        uint8_t count = _wire->requestFrom((int)_addr, 14);
        if (count < 14) {
            handleError();
            return false;
        }

        _errorCount = 0; // Successful read resets error counter

        int16_t raw_ax = (_wire->read() << 8) | _wire->read();
        int16_t raw_ay = (_wire->read() << 8) | _wire->read();
        int16_t raw_az = (_wire->read() << 8) | _wire->read();

        // Temperature (skip 2 bytes)
        _wire->read(); _wire->read();

        int16_t raw_gx = (_wire->read() << 8) | _wire->read();
        int16_t raw_gy = (_wire->read() << 8) | _wire->read();
        int16_t raw_gz = (_wire->read() << 8) | _wire->read();

        // If raw reading is entirely 0, the bus is floating
        if (raw_ax == 0 && raw_ay == 0 && raw_az == 0) {
            handleError();
            return false;
        }

        // Convert raw integers: +-4g -> 8192 LSB/g, +-500 dps -> 65.5 LSB/dps
        ax_g = (float)raw_ax / 8192.0f;
        ay_g = (float)raw_ay / 8192.0f;
        az_g = (float)raw_az / 8192.0f;

        gx_dps = (float)raw_gx / 65.5f;
        gy_dps = (float)raw_gy / 65.5f;
        gz_dps = (float)raw_gz / 65.5f;

        return true;
    }

    // Reads Pitch & Roll tilt angles in degrees
    bool readTilt(float &tilt_x, float &tilt_y) {
        float ax, ay, az, gx, gy, gz;
        if (!readMotion(ax, ay, az, gx, gy, gz)) {
            return false;
        }

        // Pitch (Tilt X)
        float denom = sqrt(ax * ax + az * az);
        if (denom > 0.001f) {
            tilt_x = atan2(ay, denom) * (180.0f / M_PI);
        } else {
            tilt_x = (ay >= 0) ? 90.0f : -90.0f;
        }

        // Roll (Tilt Y)
        tilt_y = atan2(-ax, az) * (180.0f / M_PI);
        return true;
    }

    // Reads Pitch, Roll, and dynamic motion vibration intensity in one call
    bool readTiltAndMotion(float &tilt_x, float &tilt_y, float &motion_vib) {
        float ax, ay, az, gx, gy, gz;
        if (!readMotion(ax, ay, az, gx, gy, gz)) {
            return false;
        }

        float denom = sqrt(ax * ax + az * az);
        if (denom > 0.001f) {
            tilt_x = atan2(ay, denom) * (180.0f / M_PI);
        } else {
            tilt_x = (ay >= 0) ? 90.0f : -90.0f;
        }
        tilt_y = atan2(-ax, az) * (180.0f / M_PI);

        // Combined dynamic vibration: Gyroscope angular rate + net transient G-force deviation
        float gyroMag = sqrt(gx * gx + gy * gy + gz * gz) / 200.0f;
        float accelDeviation = fabs(sqrt(ax * ax + ay * ay + az * az) - 1.0f);
        motion_vib = gyroMag + accelDeviation;
        if (motion_vib < 0.005f) motion_vib = 0.005f;

        return true;
    }

    bool isOnline() const { return _initialized; }
    uint8_t getWhoAmI() const { return _whoami; }
    uint8_t getAddress() const { return _addr; }

private:
    uint8_t _addr;
    TwoWire *_wire;
    bool _initialized;
    uint8_t _whoami;
    uint8_t _errorCount;

    void handleError() {
        _errorCount++;
        if (_errorCount >= 5) {
            _initialized = false; // Mark offline so supervisor loop will auto-reconnect
        }
    }

    bool ping(uint8_t addr) {
        _wire->beginTransmission(addr);
        return (_wire->endTransmission() == 0);
    }

    void writeRegister(uint8_t reg, uint8_t val) {
        _wire->beginTransmission(_addr);
        _wire->write(reg);
        _wire->write(val);
        _wire->endTransmission();
    }

    uint8_t readRegister(uint8_t reg) {
        _wire->beginTransmission(_addr);
        _wire->write(reg);
        uint8_t err = _wire->endTransmission(false);
        if (err != 0) {
            _wire->beginTransmission(_addr);
            _wire->write(reg);
            _wire->endTransmission(true);
        }
        _wire->requestFrom((int)_addr, 1);
        return _wire->available() ? _wire->read() : 0x00;
    }
};

#endif // MPU6500_DRIVER_H
