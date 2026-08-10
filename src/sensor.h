// ═════════════════════════════════════════════════════════════════════════════
// sensor.h — Modul Sensor Gas E-NOSE v2
// 10 sensor di 4 ADS1115:
//   ADS1 (0x48): TGS822(A1), MQ135(A2), MQ9(A3)
//   ADS2 (0x49): TGS2611(A0), TGS2620(A1)
//   ADS3 (0x4A): TGS2600(A0), TGS2602(A1)
//   ADS4 (0x4B): MQ8(A3), TGS813(A1), TGS816(A2)
// ═════════════════════════════════════════════════════════════════════════════
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <EEPROM.h>
#include "ADS1X15.h"
#include "MQUnifiedsensor.h"
#include "TGSSensor.h"

// ─── Software I2C Pins ────────────────────────────────────────────────────────
#define PIN_SDA   35
#define PIN_SCL   34

// ─── I2C Addresses (4× ADS1115) ──────────────────────────────────────────────
#define I2C_ADDR_ADS1   0x48   // ADDR → GND
#define I2C_ADDR_ADS2   0x49   // ADDR → VCC
#define I2C_ADDR_ADS3   0x4A   // ADDR → SDA
#define I2C_ADDR_ADS4   0x4B   // ADDR → SCL

// ─── ADS1115 Config ───────────────────────────────────────────────────────────
#define ADS_GAIN      0        // ±6.144 V
#define ADS_VOLTAGE   6.144
#define ADS_ADC       16

// ─── ADS1115 Channel Map ──────────────────────────────────────────────────────
// ADS1 (0x48)
#define ADS1_CHAN_TGS822   1
#define ADS1_CHAN_MQ135    2
#define ADS1_CHAN_MQ9      3
// ADS2 (0x49)
#define ADS2_CHAN_TGS2611  0
#define ADS2_CHAN_TGS2620  1
// ADS3 (0x4A)
#define ADS3_CHAN_TGS2600  0
#define ADS3_CHAN_TGS2602  1
// ADS4 (0x4B)
#define ADS4_CHAN_TGS813   1
#define ADS4_CHAN_TGS816   2
#define ADS4_CHAN_MQ8      3

// ─── EEPROM Layout (kalibrasi R0) ─────────────────────────────────────────────
#define EEPROM_MAGIC_ADDR   0
#define EEPROM_MAGIC_VALUE  0xA5
#define EEPROM_R0_ADDR      1      // 10 × float = 40 bytes (addr 1–40)

// ─── Sensor Indices ───────────────────────────────────────────────────────────
#define NUM_SENSORS      10
#define SENSOR_TGS822     0
#define SENSOR_MQ135      1
#define SENSOR_MQ9        2
#define SENSOR_TGS2611    3
#define SENSOR_TGS2620    4
#define SENSOR_TGS2600    5
#define SENSOR_TGS2602    6
#define SENSOR_MQ8        7
#define SENSOR_TGS813     8
#define SENSOR_TGS816     9

// ─── Feature Flag: PPM ────────────────────────────────────────────────────────
#ifndef USE_PPM
#define USE_PPM  0
#endif

// ═══════════════════════════════════════════════════════════════════════════════
class SensorArray {
public:
    SensorArray();

    bool begin();               // Init I2C, cek 4× ADS, konfigurasi sensor
    void calibrate();           // Kalibrasi R0 di udara bersih → simpan EEPROM
    bool loadCalibration();     // Muat R0 dari EEPROM

    void readAll();             // Baca 10 channel ADC

    uint16_t        getAdc(uint8_t idx) const { return adc_[idx]; }
    const uint16_t* getAdcArray()       const { return adc_; }

    void printJsonData(const char* phase, uint32_t cycle, uint32_t sampleIdx);

private:
    // 4× ADS1115
    ADS1115 ads1_, ads2_, ads3_, ads4_;
    bool hasAds1_ = false;
    bool hasAds2_ = false;
    bool hasAds3_ = false;
    bool hasAds4_ = false;

    // 3× MQ sensor
    MQUnifiedsensor mq135_, mq9_, mq8_;

    // 7× TGS sensor (generic library)
    TGSSensor tgs822_, tgs2620_, tgs2611_, tgs2600_, tgs2602_, tgs813_, tgs816_;

    // 10 ADC values
    uint16_t adc_[NUM_SENSORS];

    void  saveR0ToEeprom(uint8_t idx, float val);
    float loadR0FromEeprom(uint8_t idx);
};
