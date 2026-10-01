
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
#include "TaskScheduler.h"
#include "actuator.h"
#include "inference.h"
#include "nextion_transport.h"
#include "sensor.h"
#include <Arduino.h>
#include <Wire.h>
#include <stdio.h>
#include <string.h>

// ─── Konfigurasi Akuisisi
// ─────────────────────────────────────────────────────
#define ACQ_COLLECTION_SECONDS 60 // durasi menghirup aroma kopi (detik)
#define ACQ_PURGE_SECONDS 120     // durasi purging ke udara bebas (detik)
#define ACQ_REPETITIONS 40        // jumlah pengulangan siklus

// ─── Feature Flags
// ────────────────────────────────────────────────────────────
#ifndef IS_CALIBRATING_GAS_SENSOR
#define IS_CALIBRATING_GAS_SENSOR 0 // 1 hanya untuk prosedur kalibrasi terawasi
#endif

// ─── Task Scheduler Intervals
// ─────────────────────────────────────────────────
#define TASK_INTERVAL_MS_ADS 1000   // 1 sampel/detik
#define TASK_INTERVAL_MS_SERIAL 100 // polling Serial 10×/detik

// ─── State Machine
// ────────────────────────────────────────────────────────────
enum class AcqState { IDLE, COLLECTING, PURGING, PAUSED, COMPLETE };

// ═══════════════════════════════════════════════════════════════════════════════
//  Global Objects
// ═══════════════════════════════════════════════════════════════════════════════
SensorArray sensors;
Actuator actuator;
Inference inference;
Scheduler scheduler;
NextionTransport nextion(Serial1);

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
void handleNextionEvent(const char *event);
void showNextionPage(const char *pageName);
void updateNextionRunStatus();
void updateNextionSensorSnapshot();
void updateNextionInferenceResult();
void pauseAcquisition();
void resumeAcquisition();
void sendNextionAlert(const char *title, const char *message,
                      const char *action);

// ─── TaskScheduler Tasks
// ──────────────────────────────────────────────────────
Task taskAds(TASK_INTERVAL_MS_ADS, TASK_FOREVER, &adsCallback);
Task taskSerial(TASK_INTERVAL_MS_SERIAL, TASK_FOREVER, &serialCallback);

// ─── Status sensor
// ────────────────────────────────────────────────────────────
bool sensorsReady = false;
bool nextionHomeSent = false;
uint32_t nextionBootMs = 0;
char nextionPageName[16] = "pSplash";
uint8_t roastSelection = 0;
uint8_t originSelection = 0;
uint16_t batchNumber = 1;
uint8_t nextionSensorIndex = 0;

static const char *const ROAST_OPTIONS[] = {"light", "medium", "dark"};
static const char *const ORIGIN_OPTIONS[] = {"unknown", "Arabika"};
static const char *const SENSOR_UI_NAMES[NUM_SENSORS] = {
    "TGS822", "MQ135",  "MQ3",    "TGS2611", "TGS2620",
    "TGS2600", "TGS2602", "MQ8",    "TGS813",  "TGS816"};

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
  nextion.begin(115200);
  nextionBootMs = millis();

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
  Serial.println(F("  Perintah:"));
  Serial.println(F("    #start;       Mulai akuisisi data sensor"));
  Serial.println(F("    #stop;        Hentikan akuisisi"));
  Serial.println(F("    #scan;        Scan I2C bus"));
  Serial.println(F("    #valve_on;    Valve solenoid ON  (test collecting)"));
  Serial.println(F("    #valve_off;   Valve solenoid OFF (test purging)"));
  Serial.println(
      F("    #valve_test;  Toggle valve 3x untuk verifikasi wiring"));
  Serial.println(F("    #help;        Tampilkan bantuan"));
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

void pauseAcquisition() {
  if (acqState != AcqState::COLLECTING && acqState != AcqState::PURGING) {
    return;
  }
  acqState = AcqState::PAUSED;
  setActuators();
  Serial.println(F("{\"event\":\"ACQ_PAUSE\",\"phase\":\"paused\"}"));
}

void resumeAcquisition() {
  if (acqState != AcqState::PAUSED) {
    return;
  }
  acqState = AcqState::PURGING;
  acqPhaseStartMs = millis();
  setActuators();
  Serial.println(F("{\"event\":\"ACQ_RESUME\",\"phase\":\"purging\"}"));
}

void processAcquisitionState() {
  if (acqState == AcqState::IDLE || acqState == AcqState::PAUSED ||
      acqState == AcqState::COMPLETE)
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
        // Semua 10 siklus (Purging + Collecting) selesai -> COMPLETE
        acqState = AcqState::COMPLETE;
        setActuators();
        printAcquisitionSummary();
        doInference();
        updateNextionInferenceResult();
        if (strcmp(inference.predictLabel(), "N/A") != 0) {
          showNextionPage("pResult");
          nextion.text("pResult.tRConf", "Confidence N/A");
          nextion.text("pResult.tOrigin", "Origin N/A");
        } else {
          showNextionPage("pDataDone");
          nextion.text("pDataDone.tFile", "Result belum tersedia");
        }
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
  case AcqState::PAUSED:
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
  case AcqState::PAUSED:
    return "paused";
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

void showNextionPage(const char *pageName) {
  if (pageName == nullptr) {
    return;
  }
  nextion.page(pageName);
  if (strcmp(pageName, "pSplash") != 0) {
    nextionHomeSent = true;
  }
  strncpy(nextionPageName, pageName, sizeof(nextionPageName) - 1);
  nextionPageName[sizeof(nextionPageName) - 1] = '\0';
  if (strcmp(pageName, "pDataRun") == 0) {
    nextionSensorIndex = 0;
  }
}

void sendNextionAlert(const char *title, const char *message,
                      const char *action) {
  showNextionPage("pAlert");
  nextion.text("pAlert.tAlert", title);
  nextion.text("pAlert.tMsg", message);
  nextion.text("pAlert.tAction", action);
}

void updateNextionRunStatus() {
  if (strcmp(nextionPageName, "pDataRun") != 0) {
    return;
  }

  char text[32] = {};
  const uint32_t cycle = acqCycle == 0 ? 1 : acqCycle;
  const uint32_t totalSeconds =
      acqState == AcqState::PURGING ? ACQ_PURGE_SECONDS
                                    : ACQ_COLLECTION_SECONDS;
  const uint32_t elapsedSeconds = (millis() - acqPhaseStartMs) / 1000UL;
  const uint32_t remaining = elapsedSeconds < totalSeconds
                                 ? totalSeconds - elapsedSeconds
                                 : 0;
  const uint8_t cyclePercent =
      static_cast<uint8_t>((cycle * 100UL) / ACQ_REPETITIONS);

  snprintf(text, sizeof(text), "BATCH-%04u", batchNumber);
  nextion.text("pDataRun.tSample", text);
  snprintf(text, sizeof(text), "CYCLE %lu / %u", (unsigned long)cycle,
           ACQ_REPETITIONS);
  nextion.text("pDataRun.tCycle", text);
  nextion.progress("pDataRun.jCycle", cyclePercent > 100 ? 100 : cyclePercent);
  nextion.text("pDataRun.tPhase", acqStateName());
  snprintf(text, sizeof(text), "%02lu:%02lu", (unsigned long)(remaining / 60),
           (unsigned long)(remaining % 60));
  nextion.text("pDataRun.tRemain", text);
  if (sensors.environmentValid()) {
    snprintf(text, sizeof(text), "%.1f C", sensors.getTemperatureC());
    nextion.text("pDataRun.tTemp", text);
    snprintf(text, sizeof(text), "%.1f %%RH", sensors.getHumidityRh());
    nextion.text("pDataRun.tHum", text);
  } else {
    nextion.text("pDataRun.tTemp", "N/A");
    nextion.text("pDataRun.tHum", "N/A");
  }
  updateNextionSensorSnapshot();
}

void updateNextionSensorSnapshot() {
  if (strcmp(nextionPageName, "pDataRun") != 0) {
    return;
  }
  if (!sensorsReady) {
    nextion.text("pDataRun.tSensors", "ADC ERROR");
    return;
  }

  const uint8_t index = nextionSensorIndex;
  char text[24] = {};
  if (sensors.adcAvailable(index)) {
    snprintf(text, sizeof(text), "%s:%u", SENSOR_UI_NAMES[index],
             sensors.getAdc(index));
  } else {
    snprintf(text, sizeof(text), "%s:N/A", SENSOR_UI_NAMES[index]);
  }
  nextion.text("pDataRun.tSensors", text);
  nextionSensorIndex = (index + 1) % NUM_SENSORS;
}

void updateNextionInferenceResult() {
  const char *label = inference.predictLabel();
  const bool resultReady = label != nullptr && strcmp(label, "N/A") != 0;

  nextion.text("pResult.tRoast", resultReady ? label : "N/A");
  nextion.text("pResult.tRConf", "N/A");
  nextion.text("pResult.tOrigin", "N/A");
  nextion.text("pResult.tOConf", "N/A");
  nextion.progress("pResult.jLight", 0);
  nextion.progress("pResult.jMedium", 0);
  nextion.progress("pResult.jDark", 0);
}

void handleNextionEvent(const char *event) {
  if (event == nullptr || strncmp(event, "EVT:", 4) != 0) {
    return;
  }

  if (strcmp(event, "EVT:HOME") == 0) {
    if (acqState != AcqState::IDLE) {
      stopAcquisition();
    }
    showNextionPage("pHome");
  } else if (strcmp(event, "EVT:TAKE_OPEN") == 0) {
    showNextionPage("pTake");
  } else if (strcmp(event, "EVT:TEST_START") == 0) {
    showNextionPage("pTest");
  } else if (strcmp(event, "EVT:HISTORY") == 0) {
    showNextionPage("pHistory");
    nextion.text("pHistory.tH0", "History belum tersedia");
  } else if (strcmp(event, "EVT:SETTINGS") == 0) {
    showNextionPage("pSettings");
    nextion.text("pSettings.tDevId", "ATMEGA2560");
    nextion.text("pSettings.tFw", "E-NOSE v2");
  } else if (strcmp(event, "EVT:ROAST_NEXT") == 0) {
    roastSelection = (roastSelection + 1) % 3;
    nextion.text("pTake.tRoast", ROAST_OPTIONS[roastSelection]);
  } else if (strcmp(event, "EVT:ORIGIN_NEXT") == 0) {
    originSelection = (originSelection + 1) % 2;
    nextion.text("pTake.tOrigin", ORIGIN_OPTIONS[originSelection]);
  } else if (strcmp(event, "EVT:BATCH_INC") == 0) {
    if (batchNumber < 9999) {
      ++batchNumber;
    }
    char batch[24] = {};
    snprintf(batch, sizeof(batch), "BATCH-%04u", batchNumber);
    nextion.text("pTake.tBatch", batch);
  } else if (strcmp(event, "EVT:DATA_START") == 0) {
    if (acqState == AcqState::PAUSED) {
      resumeAcquisition();
    } else if (acqState == AcqState::IDLE && sensorsReady) {
      startAcquisition();
      showNextionPage("pDataRun");
    } else if (!sensorsReady) {
      sendNextionAlert("Sensor error", "ADC belum siap", "Periksa I2C lalu retry");
    } else {
      sendNextionAlert("Acquisition aktif", "Run sedang berjalan", "Gunakan pause/cancel");
    }
  } else if (strcmp(event, "EVT:DATA_PAUSE") == 0) {
    pauseAcquisition();
    updateNextionRunStatus();
  } else if (strcmp(event, "EVT:DATA_CANCEL") == 0) {
    stopAcquisition();
    showNextionPage("pHome");
  } else if (strcmp(event, "EVT:NEW_BATCH") == 0) {
    showNextionPage("pTake");
  } else if (strcmp(event, "EVT:CAL_START") == 0) {
    if (strcmp(nextionPageName, "pCal") != 0) {
      showNextionPage("pCal");
    } else {
      sendNextionAlert("Calibration locked", "Validasi chamber dan valve dulu",
                       "Calibration belum dijalankan");
    }
  } else if (strcmp(event, "EVT:AI_START") == 0) {
    showNextionPage("pTestRun");
    nextion.text("pTestRun.tPi", "Pi pending");
    nextion.text("pTestRun.tEta", "Pi protocol belum aktif");
  } else if (strcmp(event, "EVT:AI_CANCEL") == 0) {
    showNextionPage("pHome");
  } else if (strcmp(event, "EVT:RESULT_SAVE") == 0) {
    sendNextionAlert("Result pending", "Belum ada result AI valid", "Tidak ada yang disimpan");
  } else if (strcmp(event, "EVT:HISTORY_CLEAR") == 0) {
    sendNextionAlert("History locked", "Storage Pi belum terhubung", "Tidak ada yang dihapus");
  } else if (strcmp(event, "EVT:RESET") == 0) {
    sendNextionAlert("Reset locked", "Reset config perlu konfirmasi host", "Tidak ada perubahan");
  } else if (strcmp(event, "EVT:RETRY") == 0) {
    showNextionPage("pHome");
  } else if (strcmp(event, "EVT:EXIT") == 0) {
    stopAcquisition();
    sendNextionAlert("System active", "Power off dilakukan manual", "Hardware tetap aman");
  } else {
    Serial.print(F("{\"warn\":\"Unknown Nextion event\",\"event\":\""));
    Serial.print(event);
    Serial.println(F("\"}"));
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  SERIAL COMMAND PARSING
// ═══════════════════════════════════════════════════════════════════════════════

void serialCallback() {
  nextion.poll(handleNextionEvent);

  if (!nextionHomeSent && millis() - nextionBootMs >= 3000UL) {
    showNextionPage("pHome");
    nextionHomeSent = true;
  }

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
  } else if (strcmp(cmd, "#stop") == 0 || strcmp(cmd, "#0") == 0) {
    stopAcquisition();
  } else if (strcmp(cmd, "#help") == 0 || strcmp(cmd, "#2") == 0 ||
             strcmp(cmd, "#status") == 0) {
    printWelcome();
  } else if (strcmp(cmd, "#scan") == 0) {
    scanI2C();

    // ── Valve debug commands ────────────────────────────────────────────────
  } else if (strcmp(cmd, "#valve_on") == 0) {
    if (acqState != AcqState::IDLE) {
      Serial.println(
          F("{\"warn\":\"Tidak bisa tes valve saat akuisisi berjalan.\"}"));
      return;
    }
    // Aktifkan solenoid → Port 1/33 terbuka (posisi COLLECTING)
    actuator.setCollecting();
    Serial.println(
        F("{\"valve\":\"ON\",\"port\":\"1/33\",\"mode\":\"collecting\"}"));

  } else if (strcmp(cmd, "#valve_off") == 0) {
    if (acqState != AcqState::IDLE) {
      Serial.println(
          F("{\"warn\":\"Tidak bisa tes valve saat akuisisi berjalan.\"}"));
      return;
    }
    // Matikan solenoid → Port 3/11 terbuka (posisi PURGING / spring return)
    actuator.setPurging();
    Serial.println(
        F("{\"valve\":\"OFF\",\"port\":\"3/11\",\"mode\":\"purging\"}"));

  } else if (strcmp(cmd, "#valve_test") == 0) {
    if (acqState != AcqState::IDLE) {
      Serial.println(
          F("{\"warn\":\"Tidak bisa tes valve saat akuisisi berjalan.\"}"));
      return;
    }
    // Toggle valve 3x dengan jeda 1 detik — verifikasi respons fisik solenoid
    Serial.println(F("{\"valve_test\":\"start\",\"cycles\":3}"));
    for (uint8_t i = 0; i < 3; i++) {
      actuator.setCollecting();
      Serial.print(F("{\"valve_test\":\"ON\",\"cycle\":"));
      Serial.print(i + 1);
      Serial.println(F("}"));
      delay(1000);
      actuator.setPurging();
      Serial.print(F("{\"valve_test\":\"OFF\",\"cycle\":"));
      Serial.print(i + 1);
      Serial.println(F("}"));
      delay(1000);
    }
    actuator.stop();
    Serial.println(F("{\"valve_test\":\"done\"}"));

  } else if (strcmp(cmd, "#pin_scan") == 0) {
    if (acqState != AcqState::IDLE) {
      Serial.println(
          F("{\"warn\":\"Tidak bisa scan pin saat akuisisi berjalan.\"}"));
      return;
    }
    // ── Pin Scanner: cari pin mana yang terhubung ke L293DD ──────────────
    // Kandidat berdasarkan berbagai interpretasi "ATmega pin 19/20":
    //   IC TQFP Pin 19 = PB0 = Arduino 53
    //   IC TQFP Pin 20 = PB1 = Arduino 52
    //   Arduino D19 = RX1 (PJ0)
    //   Arduino D20 = SDA (PD1)
    //   IC TQFP Pin 6 = PE4 = Arduino 2
    //   IC TQFP Pin 7 = PE5 = Arduino 3
    //   Lainnya: 10,11,12,13,14
    static const uint8_t scanPins[] = {2,  3,  52, 53, 19, 20,
                                       10, 11, 12, 13, 14};
    static const uint8_t numScan = sizeof(scanPins) / sizeof(scanPins[0]);

    Serial.println(F("{\"pin_scan\":\"start\"}"));
    Serial.println(
        F("Dengarkan KLIK pada valve. Catat nomor pin yang membuatnya klik."));
    Serial.println(F("Setiap pin akan di-toggle HIGH 2 detik lalu LOW."));
    Serial.println(F("========================================="));

    for (uint8_t i = 0; i < numScan; i++) {
      uint8_t p = scanPins[i];
      pinMode(p, OUTPUT);
      digitalWrite(p, LOW);
    }
    delay(500);

    // Fase 1: Test single pin HIGH (cari pin enable atau direct drive)
    for (uint8_t i = 0; i < numScan; i++) {
      uint8_t p = scanPins[i];
      Serial.print(F(">> Pin "));
      Serial.print(p);
      Serial.println(F(" = HIGH (2 detik)..."));

      digitalWrite(p, HIGH);
      delay(2000);
      digitalWrite(p, LOW);
      delay(500);
    }

    Serial.println(F("========================================="));
    Serial.println(F("Fase 2: Test PASANGAN pin (differential H-bridge)"));
    Serial.println(F("========================================="));

    // Fase 2: Test pasangan pin (H-Bridge differential)
    // Pasangan kandidat utama
    static const uint8_t pairs[][2] = {
        {53, 52}, // PB0+PB1 (IC pin 19+20)
        {52, 53}, // reverse
        {2, 3},   // PE4+PE5 (IC pin 6+7)
        {3, 2},   // reverse
        {19, 20}, // Arduino D19+D20
        {20, 19}, // reverse
    };
    static const uint8_t numPairs = sizeof(pairs) / sizeof(pairs[0]);

    for (uint8_t i = 0; i < numPairs; i++) {
      uint8_t pA = pairs[i][0];
      uint8_t pB = pairs[i][1];

      Serial.print(F(">> Pin "));
      Serial.print(pA);
      Serial.print(F("=HIGH + Pin "));
      Serial.print(pB);
      Serial.println(F("=LOW (2 detik)..."));

      digitalWrite(pA, HIGH);
      digitalWrite(pB, LOW);
      delay(2000);
      digitalWrite(pA, LOW);
      digitalWrite(pB, LOW);
      delay(500);
    }

    // Kembalikan semua pin LOW
    for (uint8_t i = 0; i < numScan; i++) {
      digitalWrite(scanPins[i], LOW);
    }

    Serial.println(F("========================================="));
    Serial.println(F("{\"pin_scan\":\"done\"}"));
    Serial.println(
        F("Laporkan nomor pin atau pasangan yang membuat valve KLIK."));

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

  // 4. Refresh the HMI from the latest bounded snapshot.
  updateNextionRunStatus();
}
