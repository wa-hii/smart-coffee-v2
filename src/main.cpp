
// ═════════════════════════════════════════════════════════════════════════════
// Smart Coffee E-NOSE v2 — Program Utama (ATmega 2560)
//
// Portable Embedded AI untuk Standarisasi Roasting Kopi
// Klasifikasi: Light / Medium / Dark Roast
//
// Alur akuisisi per sampel:
//   PURGING (valve HIGH / Pin 10 HIGH: hembus/bilas dengan udara bersih)
//     → COLLECTING (valve LOW / Pin 10 LOW: hisap aroma sampel kopi)
//     → ulangi ACQ_REPETITIONS kali
//   Setelah semua siklus selesai → inferensi on-device (TinyML)
//
// Arsitektur modular:
//   sensor.h/cpp    — ADS1115, MQ, TGS sensors + kalibrasi EEPROM
//   actuator.h/cpp  — valve + pump PWM control
//   inference_atmega.h/cpp — feature accumulation + compact Random Forest
//   main.cpp        — state machine, serial commands, coordinator
// ═════════════════════════════════════════════════════════════════════════════
#include "TaskScheduler.h"
#include "actuator.h"
#include "inference_atmega.h"
#include "sensor.h"
#include <Arduino.h>
#include <Wire.h>

// ─── Konfigurasi Akuisisi
// ─────────────────────────────────────────────────────
#define ACQ_COLLECTION_SECONDS 120 // durasi menghirup aroma kopi (120 detik = 2 menit)
#define ACQ_PURGE_SECONDS 120      // durasi purging ke udara bebas (120 detik = 2 menit)
#define ACQ_REPETITIONS 50         // jumlah pengulangan siklus (50x)

// ─── Feature Flags
// ────────────────────────────────────────────────────────────
#ifndef IS_CALIBRATING_GAS_SENSOR
#define IS_CALIBRATING_GAS_SENSOR 1 // 1 = kalibrasi ulang, 0 = pakai EEPROM
#endif

// ─── Task Scheduler Intervals
// ─────────────────────────────────────────────────
#define TASK_INTERVAL_MS_ADS 1000   // 1 sampel/detik
#define TASK_INTERVAL_MS_SERIAL 100 // polling Serial 10×/detik

// ─── State Machine
// ────────────────────────────────────────────────────────────
enum class AcqState { IDLE, COLLECTING, PURGING, COMPLETE };

// ═══════════════════════════════════════════════════════════════════════════════
//  Global Objects
// ═══════════════════════════════════════════════════════════════════════════════
SensorArray sensors;
Actuator actuator;
InferenceATmega inference;
Scheduler scheduler;

// ─── State Akuisisi
// ───────────────────────────────────────────────────────────
AcqState acqState = AcqState::IDLE;
unsigned long acqPhaseStartMs = 0;
uint32_t acqCycle = 0;        // siklus aktif (1-based)
uint32_t acqSampleIdx = 0;    // indeks sampel dalam fase ini
uint32_t acqTotalSamples = 0; // total sampel keseluruhan

// ─── Buffer Command Serial
// ────────────────────────────────────────────────────
char cmdBuf[64] = {};
int cmdBufIdx = 0;

// ─── Forward Declarations
// ─────────────────────────────────────────────────────
void adsCallback();
void serialCallback();
void processCommand(const char *cmd);
void startAcquisition();
void stopAcquisition();
void processAcquisitionState();
void setActuators();
const char *acqStateName();
void printAcquisitionSummary();
void doInference();
void printWelcome();
void scanI2C();

// ─── TaskScheduler Tasks
// ──────────────────────────────────────────────────────
Task taskAds(TASK_INTERVAL_MS_ADS, TASK_FOREVER, &adsCallback);
Task taskSerial(TASK_INTERVAL_MS_SERIAL, TASK_FOREVER, &serialCallback);

// ─── Status sensor
// ────────────────────────────────────────────────────────────
bool sensorsReady = false;

// ═══════════════════════════════════════════════════════════════════════════════
//  scanI2C() — Scan semua alamat I2C, cetak device yang ditemukan
// ═══════════════════════════════════════════════════════════════════════════════
void scanI2C() {
  Serial.println(F(
      "{\"info\":\"Scanning I2C bus via Wire (Hardware SDA=20, SCL=21)...\"}"));
  Wire.begin();
  uint8_t count = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.print(F("{\"i2c_found\":\"0x"));
      if (addr < 16)
        Serial.print('0');
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
    Serial.println(F("{\"warn\":\"Sensor init gagal. Periksa wiring "
             "(SDA=pin20, SCL=pin21).\"}"));
    Serial.println(F("{\"warn\":\"Kirim #scan; untuk scan ulang I2C bus.\"}"));
  }

#if IS_CALIBRATING_GAS_SENSOR
  if (sensorsReady) {
    sensors.calibrate();
  }
#else
  if (sensorsReady && !sensors.loadCalibration()) {
    Serial.println(F("{\"warn\":\"Kalibrasi belum ada. Set "
                     "IS_CALIBRATING_GAS_SENSOR=1.\"}"));
  }
#endif

  scheduler.init();
  scheduler.addTask(taskAds);
  scheduler.addTask(taskSerial);
  taskAds.enable();
  taskSerial.enable();

  printWelcome();
  
  // Mulai akuisisi data secara otomatis saat alat dinyalakan/direset
  startAcquisition();
}

// ═══════════════════════════════════════════════════════════════════════════════
//  loop()
// ═══════════════════════════════════════════════════════════════════════════════
void loop() { scheduler.execute(); }

// ═══════════════════════════════════════════════════════════════════════════════
//  printWelcome() — Welcome banner
// ═══════════════════════════════════════════════════════════════════════════════
void printWelcome() {
  Serial.println();
  Serial.println(F("=============================================="));
  Serial.println(F("  Smart Coffee E-NOSE v2 - ATmega 2560"));
  Serial.println(F("=============================================="));
  Serial.println(F("  Perintah Valve Festo 3/2 (Pin 10 & 11):"));
  Serial.println(F("    #start;    Mulai siklus akuisisi otomatis"));
  Serial.println(F("    #stop;     Hentikan akuisisi / matikan valve"));
  Serial.println(F("    #on;       Nyalakan valve (Pin 10 HIGH, Pin 11 LOW)"));
  Serial.println(F("    #off;      Matikan valve (Pin 10 LOW, Pin 11 LOW)"));
  Serial.println(F("    #toggle;   Pindah status valve (ON <-> OFF)"));
  Serial.println(F("    #fwd;      Arah Forward (Pin 10 HIGH, Pin 11 LOW)"));
  Serial.println(F("    #rev;      Arah Reverse (Pin 11 HIGH, Pin 10 LOW)"));
  Serial.println(F("    #collect;  Fase collecting (Valve LOW / Kopi)"));
  Serial.println(F("    #purge;    Fase purging (Valve HIGH / Udara)"));
  Serial.println(F("    #blink;    Tes klik valve (ON-OFF 3x)"));
  Serial.println(F("    #swap;     Tukar polaritas aktif Forward <-> Reverse"));
  Serial.println(F("    #p10h; / #p10l;  Direct test Pin 10 (Pin A)"));
  Serial.println(F("    #p11h; / #p11l;  Direct test Pin 11 (Pin B)"));
  Serial.println(F("    #scan;     Scan I2C bus"));
  Serial.println(F("    #help;     Tampilkan bantuan"));
  Serial.println(F("=============================================="));
  Serial.println(
      F("{\"info\":\"Sistem siap. Kirim #start; untuk mulai akuisisi.\"}"));
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ACQUISITION STATE MACHINE
// ═══════════════════════════════════════════════════════════════════════════════

void startAcquisition() {
  acqCycle = 1;
  acqSampleIdx = 0;
  acqTotalSamples = 0;
  inference.reset();

  acqState = AcqState::PURGING;
  acqPhaseStartMs = millis();
  setActuators();

  // Event: ACQ_START
  Serial.print(F("{\"event\":\"ACQ_START\",\"phase\":\"purging\",\"cycle\":1"));
  Serial.print(F(",\"cycles_total\":"));
  Serial.print(ACQ_REPETITIONS);
  Serial.print(F(",\"collect_s\":"));
  Serial.print(ACQ_COLLECTION_SECONDS);
  Serial.print(F(",\"purge_s\":"));
  Serial.print(ACQ_PURGE_SECONDS);
  Serial.print(F(",\"total_samples_expected\":"));
  Serial.print((long)(ACQ_COLLECTION_SECONDS + ACQ_PURGE_SECONDS) *
               ACQ_REPETITIONS);
  Serial.println(F("}"));
}

void stopAcquisition() {
  acqState = AcqState::IDLE;
  acqCycle = 0;
  acqSampleIdx = 0;
  setActuators();
  Serial.println(F("{\"event\":\"ACQ_STOP\",\"phase\":\"idle\"}"));
}

void processAcquisitionState() {
  if (acqState == AcqState::IDLE || acqState == AcqState::COMPLETE)
    return;

  unsigned long elapsedMs = millis() - acqPhaseStartMs;

  if (acqState == AcqState::PURGING) {
    if (elapsedMs >= (unsigned long)ACQ_PURGE_SECONDS * 1000UL) {
      // Transisi Purging -> Collecting pada siklus yang sama (acqCycle)
      acqState = AcqState::COLLECTING;
      acqPhaseStartMs = millis();
      acqSampleIdx = 0;
      setActuators();

      Serial.print(F("{\"event\":\"PHASE_CHANGE\",\"cycle\":"));
      Serial.print(acqCycle);
      Serial.print(F(",\"phase\":\"collecting\"}"));
      Serial.println();
    }
  } else if (acqState == AcqState::COLLECTING) {
    // Akumulasi fitur untuk inferensi
    inference.accumulate(sensors.getAdcArray());

    if (elapsedMs >= (unsigned long)ACQ_COLLECTION_SECONDS * 1000UL) {
      if (acqCycle < ACQ_REPETITIONS) {
        // Lanjut ke siklus berikutnya: increment cycle -> PURGING
        acqCycle++;
        acqState = AcqState::PURGING;
        acqPhaseStartMs = millis();
        acqSampleIdx = 0;
        setActuators();

        Serial.print(F("{\"event\":\"PHASE_CHANGE\",\"cycle\":"));
        Serial.print(acqCycle);
        Serial.print(F(",\"phase\":\"purging\"}"));
        Serial.println();
      } else {
        // Semua siklus (Purging + Collecting) selesai -> COMPLETE
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
  default: // IDLE / COMPLETE
    actuator.stop();
    break;
  }
}

const char *acqStateName() {
  switch (acqState) {
  case AcqState::COLLECTING:
    return "collecting";
  case AcqState::PURGING:
    return "purging";
  case AcqState::COMPLETE:
    return "complete";
  default:
    return "idle";
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

void doInference() { inference.printResult(); }

// ═══════════════════════════════════════════════════════════════════════════════
//  SERIAL COMMAND PARSING
// ═══════════════════════════════════════════════════════════════════════════════

void serialCallback() {
  while (Serial.available()) {
    char c = (char)Serial.read();

    if (cmdBufIdx == 0 && c != '#')
      continue; // tunggu '#' pertama

    if (c == ';' || cmdBufIdx >= 62) {
      cmdBuf[cmdBufIdx] = '\0';
      processCommand(cmdBuf);
      cmdBufIdx = 0;
    } else {
      cmdBuf[cmdBufIdx++] = c;
    }
  }
}

void processCommand(const char *cmd) {
  if (strcmp(cmd, "#start") == 0 || strcmp(cmd, "#1") == 0) {
    if (acqState == AcqState::IDLE) {
      startAcquisition();
    } else {
      Serial.println(F("{\"warn\":\"Akuisisi sudah berjalan. Kirim #stop; "
                       "terlebih dahulu.\"}"));
    }
  } else if (strcmp(cmd, "#stop") == 0 || strcmp(cmd, "#0") == 0 ||
             strcmp(cmd, "#off") == 0) {
    stopAcquisition();
    actuator.stop();
    Serial.println(F("{\"event\":\"VALVE_STATE\",\"valve\":\"OFF\"}"));
  } else if (strcmp(cmd, "#on") == 0 || strcmp(cmd, "#valve_on") == 0) {
    stopAcquisition();
    actuator.valveOn();
    Serial.println(F("{\"event\":\"VALVE_STATE\",\"valve\":\"ON\",\"level\":\"HIGH\",\"pin10\":\"HIGH\",\"pin11\":\"LOW\"}"));
  } else if (strcmp(cmd, "#toggle") == 0) {
    stopAcquisition();
    actuator.toggle();
    Serial.print(F("{\"event\":\"VALVE_TOGGLE\",\"valve\":"));
    Serial.print(actuator.isValveOn() ? F("\"ON (HIGH)\"") : F("\"OFF (LOW)\""));
    Serial.println(F("}"));
  } else if (strcmp(cmd, "#collect") == 0) {
    stopAcquisition();
    actuator.setCollecting();
    Serial.println(F("{\"event\":\"VALVE_STATE\",\"mode\":\"collecting\",\"valve\":\"LOW\",\"info\":\"Jalur Sampel Kopi\"}"));
  } else if (strcmp(cmd, "#purge") == 0) {
    stopAcquisition();
    actuator.setPurging();
    Serial.println(F("{\"event\":\"VALVE_STATE\",\"mode\":\"purging\",\"valve\":\"HIGH\",\"info\":\"Jalur Udara Bersih\"}"));
  } else if (strcmp(cmd, "#fwd") == 0) {
    stopAcquisition();
    actuator.setForward();
    Serial.println(F("{\"event\":\"VALVE_STATE\",\"valve\":\"FORWARD\",\"pin10\":\"HIGH\",\"pin11\":\"LOW\"}"));
  } else if (strcmp(cmd, "#rev") == 0) {
    stopAcquisition();
    actuator.setReverse();
    Serial.println(F("{\"event\":\"VALVE_STATE\",\"valve\":\"REVERSE\",\"pin11\":\"HIGH\",\"pin10\":\"LOW\"}"));
  } else if (strcmp(cmd, "#swap") == 0 || strcmp(cmd, "#invert") == 0) {
    stopAcquisition();
    Actuator::swapPolarity();
    Serial.print(F("{\"event\":\"VALVE_POLARITY\",\"reversed\":"));
    Serial.print(Actuator::isReversed() ? F("true (Pin 11 HIGH)") : F("false (Pin 10 HIGH)"));
    Serial.println(F("}"));
  } else if (strcmp(cmd, "#invert_phase") == 0 || strcmp(cmd, "#mode") == 0) {
    stopAcquisition();
    Actuator::invertPhase();
    Serial.print(F("{\"event\":\"VALVE_MODE\",\"normallyHigh\":"));
    Serial.print(Actuator::isNormallyHigh() ? F("true") : F("false"));
    Serial.println(F("}"));
  } else if (strcmp(cmd, "#p10h") == 0 || strcmp(cmd, "#p19h") == 0) {
    stopAcquisition();
    Actuator::setDirectPin10(true);
    Serial.println(F("{\"event\":\"PIN_DIRECT\",\"pin\":\"Pin 10 (Pin A)\",\"level\":\"HIGH\"}"));
  } else if (strcmp(cmd, "#p10l") == 0 || strcmp(cmd, "#p19l") == 0) {
    stopAcquisition();
    Actuator::setDirectPin10(false);
    Serial.println(F("{\"event\":\"PIN_DIRECT\",\"pin\":\"Pin 10 (Pin A)\",\"level\":\"LOW\"}"));
  } else if (strcmp(cmd, "#p11h") == 0 || strcmp(cmd, "#p20h") == 0) {
    stopAcquisition();
    Actuator::setDirectPin11(true);
    Serial.println(F("{\"event\":\"PIN_DIRECT\",\"pin\":\"Pin 11 (Pin B)\",\"level\":\"HIGH\"}"));
  } else if (strcmp(cmd, "#p11l") == 0 || strcmp(cmd, "#p20l") == 0) {
    stopAcquisition();
    Actuator::setDirectPin11(false);
    Serial.println(F("{\"event\":\"PIN_DIRECT\",\"pin\":\"Pin 11 (Pin B)\",\"level\":\"LOW\"}"));
  } else if (strcmp(cmd, "#blink") == 0) {
    stopAcquisition();
    Serial.println(F("{\"info\":\"Diagnostic Blink: Valve Festo ON-OFF bergantian 3 kali...\"}"));
    for (int i = 0; i < 3; i++) {
      actuator.valveOn();  delay(1000);
      actuator.valveOff(); delay(1000);
    }
    actuator.stop();
    Serial.println(F("{\"info\":\"Diagnostic Blink selesai. Valve OFF.\"}"));
  } else if (strcmp(cmd, "#help") == 0 || strcmp(cmd, "#2") == 0 ||
             strcmp(cmd, "#status") == 0) {
    printWelcome();
  } else if (strcmp(cmd, "#scan") == 0) {
    scanI2C();
  } else {
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