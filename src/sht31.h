#pragma once
#include <Arduino.h>
#include <Wire.h>

// ═════════════════════════════════════════════════════════════════════════════
// SHT31Sensor — Driver I2C Sensor Suhu & Kelembapan SHT31 untuk ATmega 2560
// Alamat default: 0x44 (ADDR ke GND) atau 0x45 (ADDR ke VCC)
// Pin I2C Mega: SDA = Pin 20, SCL = Pin 21
// ═════════════════════════════════════════════════════════════════════════════

class SHT31Sensor {
public:
    SHT31Sensor() 
        : address_(0x44), isConnected_(false), lastTemp_(0.0f), lastHumidity_(0.0f) {}

    bool begin(uint8_t i2c_addr = 0x44) {
        address_ = i2c_addr;
        Wire.beginTransmission(address_);
        if (Wire.endTransmission() == 0) {
            isConnected_ = true;
            return true;
        }

        // Coba alternatif address 0x45 jika 0x44 gagal
        if (i2c_addr == 0x44) {
            Wire.beginTransmission(0x45);
            if (Wire.endTransmission() == 0) {
                address_ = 0x45;
                isConnected_ = true;
                return true;
            }
        }

        isConnected_ = false;
        return false;
    }

    bool read() {
        if (!isConnected_) {
            // Coba reconnect secara pasif
            if (!begin(address_)) {
                return false;
            }
        }

        // Kirim perintah single shot measurement, clock stretching disabled, high repeatability
        Wire.beginTransmission(address_);
        Wire.write(0x24);
        Wire.write(0x00);
        if (Wire.endTransmission() != 0) {
            isConnected_ = false;
            return false;
        }

        // Konversi high-repeatability membutuhkan maks 15 ms
        delay(16);

        if (Wire.requestFrom((uint8_t)address_, (uint8_t)6) != 6) {
            return false;
        }

        uint8_t rx[6];
        for (uint8_t i = 0; i < 6; i++) {
            rx[i] = Wire.read();
        }

        // Verifikasi CRC untuk suhu
        if (crc8(rx, 2) != rx[2]) {
            return false;
        }

        // Verifikasi CRC untuk kelembapan
        if (crc8(rx + 3, 2) != rx[5]) {
            return false;
        }

        uint16_t rawT = ((uint16_t)rx[0] << 8) | rx[1];
        uint16_t rawH = ((uint16_t)rx[3] << 8) | rx[4];

        // Rumus konversi datasheet Sensirion SHT31:
        // Temp (C) = -45 + 175 * rawT / 65535
        // Humidity (%) = 100 * rawH / 65535
        lastTemp_ = -45.0f + (175.0f * (float)rawT / 65535.0f);
        lastHumidity_ = 100.0f * (float)rawH / 65535.0f;

        if (lastHumidity_ < 0.0f) lastHumidity_ = 0.0f;
        if (lastHumidity_ > 100.0f) lastHumidity_ = 100.0f;

        return true;
    }

    bool isConnected() const { return isConnected_; }
    float getTemperature() const { return lastTemp_; }
    float getHumidity() const { return lastHumidity_; }
    uint8_t getAddress() const { return address_; }

private:
    uint8_t address_;
    bool isConnected_;
    float lastTemp_;
    float lastHumidity_;

    // CRC-8 checksum calculation (polinomial: 0x31, init: 0xFF)
    static uint8_t crc8(const uint8_t *data, uint8_t len) {
        uint8_t crc = 0xFF;
        for (uint8_t j = len; j; --j) {
            crc ^= *data++;
            for (uint8_t i = 8; i; --i) {
                crc = (crc & 0x80) ? (crc << 1) ^ 0x31 : (crc << 1);
            }
        }
        return crc;
    }
};
