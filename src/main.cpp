
// ═════════════════════════════════════════════════════════════════════════════
// Smart Coffee E-NOSE v2 — Program Utama (ATmega 2560)
//
// Portable Embedded AI untuk Standarisasi Roasting Kopi
// Klasifikasi: Light / Medium / Dark Roast
//
// Alur akuisisi per sampel:
//   COLLECTING (pompa+valve ON, ujung selang ke sampel, default 180 s)
//     → PURGING (pompa ON, valve OFF/ke udara, default 60 s)
//     → ulangi ACQ_REPETITIONS kali
//   Setelah semua siklus selesai → inferensi on-device (TinyML)
//
// Arsitektur modular:
//   sensor.h/cpp    — ADS1115, MQ, TGS sensors + kalibrasi EEPROM
//   actuator.h/cpp  — valve + pump PWM control
//   inference.h/cpp — feature accumulation + Random Forest classifier
//   main.cpp        — state machine, serial commands, coordinator
// ═════════════════════════════════════════════════════════════════════════════
#include <Arduino.h>
#include <Wire.h>
#include "TaskScheduler.h"
#include "sensor.h"
#include "actuator.h"
#include "inference.h"

// ─── Konfigurasi Akuisisi ─────────────────────────────────────────────────────
#define ACQ_COLLECTION_SECONDS  180   // durasi menghirup aroma kopi (detik)
#define ACQ_PURGE_SECONDS        60   // durasi purging ke udara bebas (detik)
#define ACQ_REPETITIONS          10   // jumlah pengulangan siklus
// Total sampel collecting: ACQ_COLLECTION_SECONDS × ACQ_REPETITIONS = 1800

// ─── Feature Flags ────────────────────────────────────────────────────────────
#ifndef IS_CALIBRATING_GAS_SENSOR
#define IS_CALIBRATING_GAS_SENSOR 1   // 1 = kalibrasi ulang, 0 = pakai EEPROM
#endif

// ─── Task Scheduler Intervals ─────────────────────────────────────────────────
#define TASK_INTERVAL_MS_ADS    1000   // 1 sampel/detik
#define TASK_INTERVAL_MS_SERIAL  100   // polling Serial 10×/detik

// ─── State Machine ────────────────────────────────────────────────────────────
enum class AcqState { IDLE, COLLECTING, PURGING, COMPLETE };

// ═══════════════════════════════════════════════════════════════════════════════
//  Global Objects
// ═══════════════════════════════════════════════════════════════════════════════
SensorArray  sensors;
Actuator     actuator;
Inference    inference;
Scheduler    scheduler;

// ─── State Akuisisi ───────────────────────────────────────────────────────────
AcqState      acqState          = AcqState::IDLE;
unsigned long acqPhaseStartMs   = 0;
uint32_t      acqCycle          = 0;     // siklus aktif (1-based)
uint32_t      acqSampleIdx      = 0;     // indeks sampel dalam fase ini
uint32_t      acqTotalSamples   = 0;     // total sampel keseluruhan

// ─── Buffer Command Serial ────────────────────────────────────────────────────
char cmdBuf[64]  = {};
int  cmdBufIdx   = 0;

// ─── Forward Declarations ─────────────────────────────────────────────────────
void adsCallback();
void serialCallback();
void processCommand(const char* cmd);
void startAcquisition();
void stopAcquisition();
void processAcquisitionState();
void setActuators();
const char* acqStateName();
void printAcquisitionSummary();
void doInference();
void printWelcome();
void scanI2C();

// ─── TaskScheduler Tasks ──────────────────────────────────────────────────────
Task taskAds   (TASK_INTERVAL_MS_ADS,    TASK_FOREVER, &adsCallback);
Task taskSerial(TASK_INTERVAL_MS_SERIAL, TASK_FOREVER, &serialCallback);

// ─── Status sensor ────────────────────────────────────────────────────────────
bool sensorsReady = false;

// ═══════════════════════════════════════════════════════════════════════════════
//  scanI2C() — Scan semua alamat I2C, cetak device yang ditemukan
// ═══════════════════════════════════════════════════════════════════════════════
void scanI2C() {
    Serial.println(F("{\"info\":\"Scanning I2C bus via Wire (Hardware SDA=20, SCL=21)...\"}"));
    Wire.begin();
    uint8_t count = 0;
    for (uint8_t addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        uint8_t err = Wire.endTransmission();
        if (err == 0) {
            Serial.print(F("{\"i2c_found\":\"0x"));
            if (addr < 16) Serial.print('0');
            Serial.print(addr, HEX);
            Serial.print(F("\",\"desc\":\""));
            if (addr >= 0x48 && addr <= 0x4B) {
                Serial.print(F("ADS1115 #"));
                Serial.print(addr - 0x48 + 1);
            } else {
                Serial.print(F("unknown"));
            }
            Serial.println(F("\"}"));
            count++;
        }
    }
    Serial.print(F("{\"i2c_scan_done\":true,\"devices_found\":"));
    Serial.print(count);
    Serial.println(F("}"));
}

// ═══════════════════════════════════════════════════════════════════════════════
//  setup()
// ═══════════════════════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);

    actuator.begin();

    // Diagnostik: scan I2C bus terlebih dahulu
    scanI2C();

    // Init sensor — TIDAK fatal jika gagal (untuk debugging)
    sensorsReady = sensors.begin();
    if (!sensorsReady) {
        Serial.println(F("{\"warn\":\"Sensor init gagal. Periksa wiring (SDA=pin35, SCL=pin34).\"}"));
        Serial.println(F("{\"warn\":\"Kirim #scan; untuk scan ulang I2C bus.\"}"));
    }

#if IS_CALIBRATING_GAS_SENSOR
    if (sensorsReady) {
        sensors.calibrate();
    }
#else
    if (sensorsReady && !sensors.loadCalibration()) {
        Serial.println(F("{\"warn\":\"Kalibrasi belum ada. Set IS_CALIBRATING_GAS_SENSOR=1.\"}"));
    }
#endif

    scheduler.init();
    scheduler.addTask(taskAds);
    scheduler.addTask(taskSerial);
    taskAds.enable();
    taskSerial.enable();

    printWelcome();
}

// ═══════════════════════════════════════════════════════════════════════════════
//  loop()
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
    scheduler.execute();
}


// ═══════════════════════════════════════════════════════════════════════════════
//  printWelcome() — Welcome banner
// ═══════════════════════════════════════════════════════════════════════════════
void printWelcome() {
    Serial.println();
    Serial.println(F("=============================================="));
    Serial.println(F("  Smart Coffee E-NOSE v2 - ATmega 2560"));
    Serial.println(F("=============================================="));
    Serial.println(F("  Perintah:"));
    Serial.println(F("    #start;  Mulai akuisisi data sensor"));
    Serial.println(F("    #stop;   Hentikan akuisisi"));
    Serial.println(F("    #scan;   Scan I2C bus"));
    Serial.println(F("    #help;   Tampilkan bantuan"));
    Serial.println(F("=============================================="));
    Serial.println(F("{\"info\":\"Sistem siap. Kirim #start; untuk mulai akuisisi.\"}"));
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ACQUISITION STATE MACHINE
// ═══════════════════════════════════════════════════════════════════════════════

void startAcquisition() {
    acqCycle        = 1;
    acqSampleIdx    = 0;
    acqTotalSamples = 0;
    inference.reset();

    acqState        = AcqState::COLLECTING;
    acqPhaseStartMs = millis();
    setActuators();

    // Event: ACQ_START
    Serial.print(F("{\"event\":\"ACQ_START\",\"phase\":\"collecting\",\"cycle\":1"));
    Serial.print(F(",\"cycles_total\":"));           Serial.print(ACQ_REPETITIONS);
    Serial.print(F(",\"collect_s\":"));              Serial.print(ACQ_COLLECTION_SECONDS);
    Serial.print(F(",\"purge_s\":"));                Serial.print(ACQ_PURGE_SECONDS);
    Serial.print(F(",\"total_samples_expected\":")); Serial.print((long)ACQ_COLLECTION_SECONDS * ACQ_REPETITIONS);
    Serial.println(F("}"));
}

void stopAcquisition() {
    acqState     = AcqState::IDLE;
    acqCycle     = 0;
    acqSampleIdx = 0;
    setActuators();
    Serial.println(F("{\"event\":\"ACQ_STOP\",\"phase\":\"idle\"}"));
}

void processAcquisitionState() {
    if (acqState == AcqState::IDLE || acqState == AcqState::COMPLETE) return;

    unsigned long elapsedMs = millis() - acqPhaseStartMs;

    if (acqState == AcqState::COLLECTING) {
        // Akumulasi fitur untuk inferensi on-device
        inference.accumulate(sensors.getAdcArray());

        if (elapsedMs >= (unsigned long)ACQ_COLLECTION_SECONDS * 1000UL) {
            // Transisi → PURGING
            acqState        = AcqState::PURGING;
            acqPhaseStartMs = millis();
            acqSampleIdx    = 0;
            setActuators();

            Serial.print(F("{\"event\":\"PHASE_CHANGE\",\"cycle\":"));
            Serial.print(acqCycle);
            Serial.print(F(",\"phase\":\"purging\"}"));
            Serial.println();
        }
    }
    else if (acqState == AcqState::PURGING) {
        if (elapsedMs >= (unsigned long)ACQ_PURGE_SECONDS * 1000UL) {
            if (acqCycle < ACQ_REPETITIONS) {
                // Transisi → COLLECTING (siklus berikutnya)
                acqCycle++;
                acqState        = AcqState::COLLECTING;
                acqPhaseStartMs = millis();
                acqSampleIdx    = 0;
                setActuators();

                Serial.print(F("{\"event\":\"PHASE_CHANGE\",\"cycle\":"));
                Serial.print(acqCycle);
                Serial.print(F(",\"phase\":\"collecting\"}"));
                Serial.println();
            } else {
                // Semua siklus selesai → COMPLETE
                acqState = AcqState::COMPLETE;
                setActuators();
                printAcquisitionSummary();
                doInference();
                acqState = AcqState::IDLE;
            }
        }
    }
}

void setActuators() {
    switch (acqState) {
        case AcqState::COLLECTING:
            actuator.setCollecting();
            break;
        case AcqState::PURGING:
            actuator.setPurging();
            break;
        default:  // IDLE / COMPLETE
            actuator.stop();
            break;
    }
}

const char* acqStateName() {
    switch (acqState) {
        case AcqState::COLLECTING: return "collecting";
        case AcqState::PURGING:    return "purging";
        case AcqState::COMPLETE:   return "complete";
        default:                   return "idle";
    }
}

void printAcquisitionSummary() {
    Serial.print(F("{\"event\":\"ACQ_COMPLETE\",\"cycles\":"));
    Serial.print(ACQ_REPETITIONS);
    Serial.print(F(",\"total_samples\":"));
    Serial.print(acqTotalSamples);
    Serial.print(F(",\"feat_count\":"));
    Serial.print(inference.getFeatureCount());
    Serial.println(F("}"));
}

void doInference() {
    inference.printResult();
}

// ═══════════════════════════════════════════════════════════════════════════════
//  SERIAL COMMAND PARSING
// ═══════════════════════════════════════════════════════════════════════════════

void serialCallback() {
    while (Serial.available()) {
        char c = (char)Serial.read();

        if (cmdBufIdx == 0 && c != '#') continue;   // tunggu '#' pertama

        if (c == ';' || cmdBufIdx >= 62) {
            cmdBuf[cmdBufIdx] = '\0';
            processCommand(cmdBuf);
            cmdBufIdx = 0;
        } else {
            cmdBuf[cmdBufIdx++] = c;
        }
    }
}

void processCommand(const char* cmd) {
    if (strcmp(cmd, "#start") == 0 || strcmp(cmd, "#1") == 0) {
        if (acqState == AcqState::IDLE) {
            startAcquisition();
        } else {
            Serial.println(F("{\"warn\":\"Akuisisi sudah berjalan. Kirim #stop; terlebih dahulu.\"}"));
        }
    }
    else if (strcmp(cmd, "#stop") == 0 || strcmp(cmd, "#0") == 0) {
        stopAcquisition();
    }
    else if (strcmp(cmd, "#help") == 0 || strcmp(cmd, "#2") == 0 || strcmp(cmd, "#status") == 0) {
        printWelcome();
    }
    else if (strcmp(cmd, "#scan") == 0) {
        scanI2C();
    }
    else {
        Serial.print(F("{\"warn\":\"Perintah tidak dikenal\",\"cmd\":\""));
        Serial.print(cmd);
        Serial.println(F("\"}"));
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ADS CALLBACK — Baca semua sensor, proses state machine, kirim JSON
// ═══════════════════════════════════════════════════════════════════════════════

void adsCallback() {
    // 1. Baca semua ADC
    sensors.readAll();

    // 2. Update state machine (transisi fase, akumulasi fitur)
    processAcquisitionState();
    acqSampleIdx++;
    if (acqState == AcqState::COLLECTING || acqState == AcqState::PURGING) {
        acqTotalSamples++;
    }

    // 3. Kirim JSON sensor data
    sensors.printJsonData(acqStateName(), acqCycle, acqSampleIdx);
}