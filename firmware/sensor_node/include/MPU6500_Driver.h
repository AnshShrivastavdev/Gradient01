#ifndef MPU6500_DRIVER_H
#define MPU6500_DRIVER_H

#include <Arduino.h>
#include <Wire.h>
#include <math.h>

// ================================================================
// SIH 2026 - Underground Coal Mine Monitoring System
// MPU6500 6-DOF INCLINOMETER & ACCELEROMETER DRIVER
// Team Gradient
//
// Features:
//   - Native I2C driver for InvenSense MPU6500 (WHO_AM_I = 0x70)
//   - Backwards compatible with MPU9250 (0x71/0x73) and MPU6050 (0x68)
//   - Dynamic address detection (0x68 primary, 0x69 secondary)
//   - Hardware Digital Low Pass Filter (DLPF ~20-40 Hz)
//   - Built-in Pitch / Roll tilt angle calculation
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
#define MPU6500_REG_PWR_MGMT_1    0x6B
#define MPU6500_REG_PWR_MGMT_2    0x6C
#define MPU6500_REG_WHO_AM_I      0x75

class MPU6500Driver {
public:
    MPU6500Driver() : _addr(MPU6500_DEFAULT_ADDR), _wire(&Wire), _initialized(false), _whoami(0) {}

    bool begin(uint8_t preferred_addr = MPU6500_DEFAULT_ADDR, TwoWire *wire = &Wire) {
        _wire = wire;
        _initialized = false;

        // Try preferred address first, fallback to alternate
        if (ping(preferred_addr)) {
            _addr = preferred_addr;
        } else {
            uint8_t alt = (preferred_addr == MPU6500_DEFAULT_ADDR) ? MPU6500_ALT_ADDR : MPU6500_DEFAULT_ADDR;
            if (ping(alt)) {
                _addr = alt;
            } else {
                Serial.printf("[MPU6500] Sensor not responding on 0x%02X or 0x%02X\n", preferred_addr, alt);
                return false;
            }
        }

        // Reset device
        writeRegister(MPU6500_REG_PWR_MGMT_1, 0x80);
        delay(100);

        // Wake up device, select best available PLL clock source (Auto 0x01)
        writeRegister(MPU6500_REG_PWR_MGMT_1, 0x01);
        delay(15);

        // Read WHO_AM_I
        _whoami = readRegister(MPU6500_REG_WHO_AM_I);
        Serial.printf("[MPU6500] Detected I2C device at 0x%02X with WHO_AM_I = 0x%02X\n", _addr, _whoami);

        // Validate chip ID:
        // 0x70 = Genuine MPU6500
        // 0x71 / 0x73 = MPU9250 / MPU6500 variant
        // 0x68 = MPU6050 fallback
        if (_whoami == 0x00 || _whoami == 0xFF) {
            Serial.println("[MPU6500] ERROR: Invalid WHO_AM_I (bus disconnected or float)");
            return false;
        }

        // DLPF Config: Bandwidth ~42Hz
        writeRegister(MPU6500_REG_CONFIG, 0x03);

        // Sample rate divider: 1kHz / (1 + 4) = 200 Hz
        writeRegister(MPU6500_REG_SMPLRT_DIV, 0x04);

        // Gyro Config: +-500 deg/s (FS_SEL = 1 -> 0x08)
        writeRegister(MPU6500_REG_GYRO_CONFIG, 0x08);

        // Accel Config: +-4g (AFS_SEL = 1 -> 0x08)
        writeRegister(MPU6500_REG_ACCEL_CONFIG, 0x08);

        // If MPU6500, set Accel DLPF to ~44.8 Hz (ACCEL_CONFIG2)
        if (_whoami >= 0x70) {
            writeRegister(MPU6500_REG_ACCEL_CONFIG2, 0x03);
        }

        _initialized = true;
        Serial.println("[MPU6500] Initialization successful (±4g, ±500 dps, DLPF active).");
        return true;
    }

    bool readMotion(float &ax_g, float &ay_g, float &az_g, float &gx_dps, float &gy_dps, float &gz_dps) {
        if (!_initialized) return false;

        _wire->beginTransmission(_addr);
        _wire->write(MPU6500_REG_ACCEL_XOUT_H);
        if (_wire->endTransmission(false) != 0) return false;

        if (_wire->requestFrom(_addr, (uint8_t)14) != 14) return false;

        int16_t raw_ax = (_wire->read() << 8) | _wire->read();
        int16_t raw_ay = (_wire->read() << 8) | _wire->read();
        int16_t raw_az = (_wire->read() << 8) | _wire->read();

        // Skip temperature bytes (TEMP_OUT_H, TEMP_OUT_L)
        _wire->read();
        _wire->read();

        int16_t raw_gx = (_wire->read() << 8) | _wire->read();
        int16_t raw_gy = (_wire->read() << 8) | _wire->read();
        int16_t raw_gz = (_wire->read() << 8) | _wire->read();

        // Sensitivity: +-4g -> 8192 LSB/g, +-500 dps -> 65.5 LSB/dps
        ax_g = (float)raw_ax / 8192.0f;
        ay_g = (float)raw_ay / 8192.0f;
        az_g = (float)raw_az / 8192.0f;

        gx_dps = (float)raw_gx / 65.5f;
        gy_dps = (float)raw_gy / 65.5f;
        gz_dps = (float)raw_gz / 65.5f;

        return true;
    }

    bool readTilt(float &tilt_x, float &tilt_y) {
        float ax, ay, az, gx, gy, gz;
        if (!readMotion(ax, ay, az, gx, gy, gz)) {
            return false;
        }

        // Calculate Pitch (Tilt X) and Roll (Tilt Y) angles in degrees
        // pitch = atan2(ay, sqrt(ax^2 + az^2)) * (180.0 / PI)
        // roll  = atan2(-ax, az) * (180.0 / PI)
        tilt_x = atan2(ay, sqrt(ax * ax + az * az)) * (180.0f / PI);
        tilt_y = atan2(-ax, az) * (180.0f / PI);
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
        if (_wire->endTransmission(false) != 0) {
            return 0x00;
        }
        if (_wire->requestFrom(_addr, (uint8_t)1) != 1) {
            return 0x00;
        }
        return _wire->available() ? _wire->read() : 0x00;
    }
};

#endif // MPU6500_DRIVER_H
