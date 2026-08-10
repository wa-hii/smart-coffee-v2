// ═════════════════════════════════════════════════════════════════════════════
// sensor.cpp — Implementasi Modul Sensor Gas E-NOSE v2
//
// 10 sensor di 4 ADS1115:
//   ADS1 (0x48): TGS822(A1), MQ135(A2), MQ9(A3)
//   ADS2 (0x49): TGS2611(A0), TGS2620(A1)
//   ADS3 (0x4A): TGS2600(A0), TGS2602(A1)
//   ADS4 (0x4B): MQ8(A3), TGS813(A1), TGS816(A2)
// ═════════════════════════════════════════════════════════════════════════════
#include "sensor.h"

// ─── Konstanta Kalibrasi ──────────────────────────────────────────────────────
// RL (kΩ) dan rasio Rs/R0 di udara bersih per sensor
// Nilai default dari datasheet — sesuaikan jika sirkuit berbeda
static const float SENSOR_RL[] = {
    20.0,   // TGS822
    20.0,   // MQ135
    20.0,   // MQ9
    20.0,   // TGS2611
    20.0,   // TGS2620
    20.0,   // TGS2600
    0.45,   // TGS2602  (RL kecil sesuai desain sirkuit)
    10.0,   // MQ8
    20.0,   // TGS813
    20.0,   // TGS816
};

static const float RATIO_AIR[] = {
    17.0,   // TGS822
    3.6,    // MQ135
    9.6,    // MQ9
    19.0,   // TGS2611
    21.0,   // TGS2620
    10.0,   // TGS2600
    1.0,    // TGS2602  (default, R0 ditentukan saat kalibrasi)
    70.0,   // MQ8
    14.0,   // TGS813
    14.0,   // TGS816
};

// ─────────────────────────────────────────────────────────────────────────────
//  Constructor
// ─────────────────────────────────────────────────────────────────────────────
SensorArray::SensorArray()
    : ads1_(I2C_ADDR_ADS1)
    , ads2_(I2C_ADDR_ADS2)
    , ads3_(I2C_ADDR_ADS3)
    , ads4_(I2C_ADDR_ADS4)
    , mq135_("ATmega2560", ADS_VOLTAGE, ADS_ADC, 0, "MQ-135")
    , mq9_  ("ATmega2560", ADS_VOLTAGE, ADS_ADC, 0, "MQ-9")
    , mq8_  ("ATmega2560", ADS_VOLTAGE, ADS_ADC, 0, "MQ-8")
{
    memset(adc_, 0, sizeof(adc_));
}

// ─────────────────────────────────────────────────────────────────────────────
//  begin() — Inisialisasi hardware sensor
// ─────────────────────────────────────────────────────────────────────────────
bool SensorArray::begin() {
    Wire.begin();

    hasAds1_ = ads1_.begin();
    hasAds2_ = ads2_.begin();
    hasAds3_ = ads3_.begin();
    hasAds4_ = ads4_.begin();

    uint8_t foundCount = 0;

    if (hasAds1_) { ads1_.setGain(ADS_GAIN); foundCount++; }
    else { Serial.println(F("{\"warn\":\"ADS1115 #1 (0x48) tidak terdeteksi\"}")); }

    if (hasAds2_) { ads2_.setGain(ADS_GAIN); foundCount++; }
    else { Serial.println(F("{\"warn\":\"ADS1115 #2 (0x49) tidak terdeteksi\"}")); }

    if (hasAds3_) { ads3_.setGain(ADS_GAIN); foundCount++; }
    else { Serial.println(F("{\"warn\":\"ADS1115 #3 (0x4A) tidak terdeteksi\"}")); }

    if (hasAds4_) { ads4_.setGain(ADS_GAIN); foundCount++; }
    else { Serial.println(F("{\"warn\":\"ADS1115 #4 (0x4B) tidak terdeteksi\"}")); }

    Serial.print(F("{\"info\":\"ADS1115 terdeteksi: "));
    Serial.print(foundCount);
    Serial.println(F("/4\"}"));

    // ── Konfigurasi MQ sensors ───────────────────────────────────────────────
    mq135_.setRegressionMethod(1); mq135_.setRL(SENSOR_RL[SENSOR_MQ135]);
    mq9_.setRegressionMethod(1);   mq9_.setRL(SENSOR_RL[SENSOR_MQ9]);
    mq8_.setRegressionMethod(1);   mq8_.setRL(SENSOR_RL[SENSOR_MQ8]);

    // ── Konfigurasi TGS sensors ──────────────────────────────────────────────
    tgs822_.setRL(SENSOR_RL[SENSOR_TGS822]);    tgs822_.setRatioAir(RATIO_AIR[SENSOR_TGS822]);
    tgs2620_.setRL(SENSOR_RL[SENSOR_TGS2620]);  tgs2620_.setRatioAir(RATIO_AIR[SENSOR_TGS2620]);
    tgs2611_.setRL(SENSOR_RL[SENSOR_TGS2611]);  tgs2611_.setRatioAir(RATIO_AIR[SENSOR_TGS2611]);
    tgs2600_.setRL(SENSOR_RL[SENSOR_TGS2600]);  tgs2600_.setRatioAir(RATIO_AIR[SENSOR_TGS2600]);
    tgs2602_.setRL(SENSOR_RL[SENSOR_TGS2602]);  tgs2602_.setRatioAir(RATIO_AIR[SENSOR_TGS2602]);
    tgs813_.setRL(SENSOR_RL[SENSOR_TGS813]);    tgs813_.setRatioAir(RATIO_AIR[SENSOR_TGS813]);
    tgs816_.setRL(SENSOR_RL[SENSOR_TGS816]);    tgs816_.setRatioAir(RATIO_AIR[SENSOR_TGS816]);

    return (foundCount > 0);
}

// ─────────────────────────────────────────────────────────────────────────────
//  calibrate() — Kalibrasi R0 di udara bersih, simpan ke EEPROM
// ─────────────────────────────────────────────────────────────────────────────
void SensorArray::calibrate() {
    Serial.println(F("{\"info\":\"Kalibrasi sensor gas di udara bersih...\"}"));
    float calc_r0;

    // ── ADS1 ──────────────────────────────────────────────────────────────────
    if (hasAds1_) {
        // TGS822
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_TGS822] = ads1_.readADC(ADS1_CHAN_TGS822);
            tgs822_.setADC(adc_[SENSOR_TGS822]);
            calc_r0 += tgs822_.calibrate(RATIO_AIR[SENSOR_TGS822]);
        }
        tgs822_.setR0(calc_r0 / SENSOR_RL[SENSOR_TGS822]);
        saveR0ToEeprom(SENSOR_TGS822, calc_r0);

        // MQ135
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_MQ135] = ads1_.readADC(ADS1_CHAN_MQ135);
            mq135_.setADC(adc_[SENSOR_MQ135]);
            calc_r0 += mq135_.calibrate(RATIO_AIR[SENSOR_MQ135]);
        }
        mq135_.setR0(calc_r0 / SENSOR_RL[SENSOR_MQ135]);
        saveR0ToEeprom(SENSOR_MQ135, calc_r0);

        // MQ9
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_MQ9] = ads1_.readADC(ADS1_CHAN_MQ9);
            mq9_.setADC(adc_[SENSOR_MQ9]);
            calc_r0 += mq9_.calibrate(RATIO_AIR[SENSOR_MQ9]);
        }
        mq9_.setR0(calc_r0 / SENSOR_RL[SENSOR_MQ9]);
        saveR0ToEeprom(SENSOR_MQ9, calc_r0);
    }

    // ── ADS2 ──────────────────────────────────────────────────────────────────
    if (hasAds2_) {
        // TGS2611
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_TGS2611] = ads2_.readADC(ADS2_CHAN_TGS2611);
            tgs2611_.setADC(adc_[SENSOR_TGS2611]);
            calc_r0 += tgs2611_.calibrate(RATIO_AIR[SENSOR_TGS2611]);
        }
        tgs2611_.setR0(calc_r0 / SENSOR_RL[SENSOR_TGS2611]);
        saveR0ToEeprom(SENSOR_TGS2611, calc_r0);

        // TGS2620
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_TGS2620] = ads2_.readADC(ADS2_CHAN_TGS2620);
            tgs2620_.setADC(adc_[SENSOR_TGS2620]);
            calc_r0 += tgs2620_.calibrate(RATIO_AIR[SENSOR_TGS2620]);
        }
        tgs2620_.setR0(calc_r0 / SENSOR_RL[SENSOR_TGS2620]);
        saveR0ToEeprom(SENSOR_TGS2620, calc_r0);
    }

    // ── ADS3 ──────────────────────────────────────────────────────────────────
    if (hasAds3_) {
        // TGS2600
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_TGS2600] = ads3_.readADC(ADS3_CHAN_TGS2600);
            tgs2600_.setADC(adc_[SENSOR_TGS2600]);
            calc_r0 += tgs2600_.calibrate(RATIO_AIR[SENSOR_TGS2600]);
        }
        tgs2600_.setR0(calc_r0 / SENSOR_RL[SENSOR_TGS2600]);
        saveR0ToEeprom(SENSOR_TGS2600, calc_r0);

        // TGS2602
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_TGS2602] = ads3_.readADC(ADS3_CHAN_TGS2602);
            tgs2602_.setADC(adc_[SENSOR_TGS2602]);
            calc_r0 += tgs2602_.calibrate(RATIO_AIR[SENSOR_TGS2602]);
        }
        tgs2602_.setR0(calc_r0 / SENSOR_RL[SENSOR_TGS2602]);
        saveR0ToEeprom(SENSOR_TGS2602, calc_r0);
    }

    // ── ADS4 ──────────────────────────────────────────────────────────────────
    if (hasAds4_) {
        // MQ8
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_MQ8] = ads4_.readADC(ADS4_CHAN_MQ8);
            mq8_.setADC(adc_[SENSOR_MQ8]);
            calc_r0 += mq8_.calibrate(RATIO_AIR[SENSOR_MQ8]);
        }
        mq8_.setR0(calc_r0 / SENSOR_RL[SENSOR_MQ8]);
        saveR0ToEeprom(SENSOR_MQ8, calc_r0);

        // TGS813
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_TGS813] = ads4_.readADC(ADS4_CHAN_TGS813);
            tgs813_.setADC(adc_[SENSOR_TGS813]);
            calc_r0 += tgs813_.calibrate(RATIO_AIR[SENSOR_TGS813]);
        }
        tgs813_.setR0(calc_r0 / SENSOR_RL[SENSOR_TGS813]);
        saveR0ToEeprom(SENSOR_TGS813, calc_r0);

        // TGS816
        calc_r0 = 0;
        for (int i = 0; i < 10; i++) {
            adc_[SENSOR_TGS816] = ads4_.readADC(ADS4_CHAN_TGS816);
            tgs816_.setADC(adc_[SENSOR_TGS816]);
            calc_r0 += tgs816_.calibrate(RATIO_AIR[SENSOR_TGS816]);
        }
        tgs816_.setR0(calc_r0 / SENSOR_RL[SENSOR_TGS816]);
        saveR0ToEeprom(SENSOR_TGS816, calc_r0);
    }

    // Tandai EEPROM sebagai valid
    EEPROM.write(EEPROM_MAGIC_ADDR, EEPROM_MAGIC_VALUE);
    Serial.println(F("{\"info\":\"Kalibrasi sensor terhubung selesai\"}"));
}

// ─────────────────────────────────────────────────────────────────────────────
//  loadCalibration() — Muat R0 dari EEPROM
// ─────────────────────────────────────────────────────────────────────────────
bool SensorArray::loadCalibration() {
    if (EEPROM.read(EEPROM_MAGIC_ADDR) != EEPROM_MAGIC_VALUE) {
        Serial.println(F("{\"error\":\"Sensor belum dikalibrasi. "
                         "Set IS_CALIBRATING_GAS_SENSOR=1, flash di udara bersih.\"}"));
        return false;
    }

    float r0;

    // MQ sensors
    r0 = loadR0FromEeprom(SENSOR_MQ135); if (r0 <= 0) return false;
    mq135_.setR0(r0 / SENSOR_RL[SENSOR_MQ135]);

    r0 = loadR0FromEeprom(SENSOR_MQ9);   if (r0 <= 0) return false;
    mq9_.setR0(r0 / SENSOR_RL[SENSOR_MQ9]);

    r0 = loadR0FromEeprom(SENSOR_MQ8);   if (r0 <= 0) return false;
    mq8_.setR0(r0 / SENSOR_RL[SENSOR_MQ8]);

    // TGS sensors
    r0 = loadR0FromEeprom(SENSOR_TGS822);  if (r0 <= 0) return false;
    tgs822_.setR0(r0 / SENSOR_RL[SENSOR_TGS822]);

    r0 = loadR0FromEeprom(SENSOR_TGS2620); if (r0 <= 0) return false;
    tgs2620_.setR0(r0 / SENSOR_RL[SENSOR_TGS2620]);

    r0 = loadR0FromEeprom(SENSOR_TGS2611); if (r0 <= 0) return false;
    tgs2611_.setR0(r0 / SENSOR_RL[SENSOR_TGS2611]);

    r0 = loadR0FromEeprom(SENSOR_TGS2600); if (r0 <= 0) return false;
    tgs2600_.setR0(r0 / SENSOR_RL[SENSOR_TGS2600]);

    r0 = loadR0FromEeprom(SENSOR_TGS2602); if (r0 <= 0) return false;
    tgs2602_.setR0(r0 / SENSOR_RL[SENSOR_TGS2602]);

    r0 = loadR0FromEeprom(SENSOR_TGS813);  if (r0 <= 0) return false;
    tgs813_.setR0(r0 / SENSOR_RL[SENSOR_TGS813]);

    r0 = loadR0FromEeprom(SENSOR_TGS816);  if (r0 <= 0) return false;
    tgs816_.setR0(r0 / SENSOR_RL[SENSOR_TGS816]);

    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
//  readAll() — Baca 10 channel ADC dari 4× ADS1115
// ─────────────────────────────────────────────────────────────────────────────
void SensorArray::readAll() {
    // ADS1 (0x48)
    if (hasAds1_) {
        adc_[SENSOR_TGS822]  = ads1_.readADC(ADS1_CHAN_TGS822);
        adc_[SENSOR_MQ135]   = ads1_.readADC(ADS1_CHAN_MQ135);
        adc_[SENSOR_MQ9]     = ads1_.readADC(ADS1_CHAN_MQ9);
    } else {
        adc_[SENSOR_TGS822] = 0; adc_[SENSOR_MQ135] = 0; adc_[SENSOR_MQ9] = 0;
    }

    // ADS2 (0x49)
    if (hasAds2_) {
        adc_[SENSOR_TGS2611] = ads2_.readADC(ADS2_CHAN_TGS2611);
        adc_[SENSOR_TGS2620] = ads2_.readADC(ADS2_CHAN_TGS2620);
    } else {
        adc_[SENSOR_TGS2611] = 0; adc_[SENSOR_TGS2620] = 0;
    }

    // ADS3 (0x4A)
    if (hasAds3_) {
        adc_[SENSOR_TGS2600] = ads3_.readADC(ADS3_CHAN_TGS2600);
        adc_[SENSOR_TGS2602] = ads3_.readADC(ADS3_CHAN_TGS2602);
    } else {
        adc_[SENSOR_TGS2600] = 0; adc_[SENSOR_TGS2602] = 0;
    }

    // ADS4 (0x4B)
    if (hasAds4_) {
        adc_[SENSOR_MQ8]     = ads4_.readADC(ADS4_CHAN_MQ8);
        adc_[SENSOR_TGS813]  = ads4_.readADC(ADS4_CHAN_TGS813);
        adc_[SENSOR_TGS816]  = ads4_.readADC(ADS4_CHAN_TGS816);
    } else {
        adc_[SENSOR_MQ8] = 0; adc_[SENSOR_TGS813] = 0; adc_[SENSOR_TGS816] = 0;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  printJsonData() — Output JSON sensor data via Serial.print()
//  F() macro → string disimpan di PROGMEM (hemat RAM)
// ─────────────────────────────────────────────────────────────────────────────
void SensorArray::printJsonData(const char* phase, uint32_t cycle, uint32_t sampleIdx) {
    Serial.print(F("{\"phase\":\""));     Serial.print(phase);
    Serial.print(F("\",\"cycle\":"));     Serial.print(cycle);
    Serial.print(F(",\"sample_idx\":")); Serial.print(sampleIdx);
    Serial.print(F(",\"timestamp\":"));  Serial.print(millis());

    // 10 ADC values
    Serial.print(F(",\"adc_tgs822\":"));  Serial.print(adc_[SENSOR_TGS822]);
    Serial.print(F(",\"adc_mq135\":"));   Serial.print(adc_[SENSOR_MQ135]);
    Serial.print(F(",\"adc_mq9\":"));     Serial.print(adc_[SENSOR_MQ9]);
    Serial.print(F(",\"adc_tgs2611\":")); Serial.print(adc_[SENSOR_TGS2611]);
    Serial.print(F(",\"adc_tgs2620\":")); Serial.print(adc_[SENSOR_TGS2620]);
    Serial.print(F(",\"adc_tgs2600\":")); Serial.print(adc_[SENSOR_TGS2600]);
    Serial.print(F(",\"adc_tgs2602\":")); Serial.print(adc_[SENSOR_TGS2602]);
    Serial.print(F(",\"adc_mq8\":"));     Serial.print(adc_[SENSOR_MQ8]);
    Serial.print(F(",\"adc_tgs813\":"));  Serial.print(adc_[SENSOR_TGS813]);
    Serial.print(F(",\"adc_tgs816\":"));  Serial.print(adc_[SENSOR_TGS816]);

#if USE_PPM
    // TODO: Tambahkan perhitungan PPM per gas jika diperlukan
    // Contoh MQ135:
    //   mq135_.setADC(adc_[SENSOR_MQ135]);
    //   mq135_.setA(605.18); mq135_.setB(-3.937);
    //   float ppm = mq135_.readSensor();
    //   Serial.print(F(",\"mq135_co\":")); Serial.print(ppm);
#endif

    Serial.println(F("}"));
}

// ─────────────────────────────────────────────────────────────────────────────
//  EEPROM helpers
// ─────────────────────────────────────────────────────────────────────────────
void SensorArray::saveR0ToEeprom(uint8_t idx, float val) {
    int addr = EEPROM_R0_ADDR + idx * sizeof(float);
    EEPROM.put(addr, val);
}

float SensorArray::loadR0FromEeprom(uint8_t idx) {
    float val;
    int addr = EEPROM_R0_ADDR + idx * sizeof(float);
    EEPROM.get(addr, val);
    return val;
}
