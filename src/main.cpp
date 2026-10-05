
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
#define ACQ_COLLECTION_SECONDS 5 // durasi menghirup aroma kopi (detik)
#define ACQ_PURGE_SECONDS 25     // durasi purging ke udara bebas (detik)
#define ACQ_REPETITIONS 5        // jumlah pengulangan siklus

// ─── Feature Flags
// ────────────────────────────────────────────────────────────
#ifndef IS_CALIBRATING_GAS_SENSOR
#define IS_CALIBRATING_GAS_SENSOR 0 // 1 hanya untuk prosedur kalibrasi terawasi
#endif

// ─── Task Scheduler Intervals
// ─────────────────────────────────────────────────
#define TASK_INTERVAL_MS_ADS 1000   // 1 sampel/detik
#define TASK_INTERVAL_MS_SERIAL 100 // polling Serial 10×/detik
#define NEXTION_BAUD 9600UL         // harus sama dengan baud project HMI aktif

// ─── State Machine
// ────────────────────────────────────────────────────────────
enum class AcqState { IDLE, COLLECTING, PURGING, PAUSED, COMPLETE };
enum class AcquisitionMode { NONE, LABELED_DATA, AI_TEST };

// ═══════════════════════════════════════════════════════════════════════════════
//  Global Objects
// ═══════════════════════════════════════════════════════════════════════════════
SensorArray sensors;
Actuator actuator;
Inference inference;
Scheduler scheduler;
NextionTransport nextion(Serial2);

// ─── State Akuisisi
// ───────────────────────────────────────────────────────────
AcqState acqState = AcqState::IDLE;
AcqState acqStateBeforePause = AcqState::IDLE;
AcquisitionMode acqMode = AcquisitionMode::NONE;
unsigned long acqPhaseStartMs = 0;
unsigned long acqPausedElapsedMs = 0;
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
void startAcquisition(AcquisitionMode mode = AcquisitionMode::LABELED_DATA);
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
void updateNextionTakePage();
void updateNextionTestPage();
void updateNextionHistoryPage();
void updateNextionSettingsPage();
void updateNextionTestRunPage();
void updateNextionTestRunStatus();
void updateNextionCalibrationPage();
void updateNextionRunStatus();
void updateNextionSensorSnapshot();
void updateNextionInferenceResult();
void buildTakeFilename(char *buffer, size_t size, bool withExtension = true);
void pauseAcquisition();
void resumeAcquisition();
void sendNextionAlert(const char *title, const char *message,
                      const char *action);
void addUiHistory(const char *entry);
void exportUiHistory();
void resetUiSettings();

// ─── TaskScheduler Tasks
// ──────────────────────────────────────────────────────
Task taskAds(TASK_INTERVAL_MS_ADS, TASK_FOREVER, &adsCallback);
Task taskSerial(TASK_INTERVAL_MS_SERIAL, TASK_FOREVER, &serialCallback);

// ─── Status sensor
// ────────────────────────────────────────────────────────────
bool sensorsReady = false;
bool calibrationReady = false;
bool nextionHomeSent = false;
uint32_t nextionBootMs = 0;
char nextionPageName[16] = "pSplash";
uint8_t roastSelection = 0;
uint8_t originSelection = 0;
// Baseline akuisisi aktif dimulai dari B32. NEXT/BATCH +/- tetap dapat
// digunakan untuk batch berikutnya.
uint16_t batchNumber = 32;
uint8_t nextionSensorIndex = 0;
uint16_t testSequence = 1;

static constexpr uint16_t NEXTION_STATUS_GREEN = 13867; // RGB565(52,199,94)
static constexpr uint16_t NEXTION_STATUS_RED = 63943;   // RGB565(255,56,60)
static constexpr uint8_t UI_HISTORY_CAPACITY = 4;
static constexpr uint8_t UI_HISTORY_TEXT_CAPACITY = 54;
char uiHistory[UI_HISTORY_CAPACITY][UI_HISTORY_TEXT_CAPACITY] = {};
uint8_t uiHistoryCount = 0;

static const char *const ROAST_OPTIONS[] = {"LIGHT", "MEDIUM", "DARK"};
static const char *const ORIGIN_OPTIONS[] = {
    "MING", "MAN", "RAT", "GAY", "MER", "TEM",
    "CAT",  "GAW", "TIM", "BAR", "MUK", "CAW",
    "GRB",  "TOR"};
static constexpr uint8_t ROAST_OPTION_COUNT =
    sizeof(ROAST_OPTIONS) / sizeof(ROAST_OPTIONS[0]);
static constexpr uint8_t ORIGIN_OPTION_COUNT =
    sizeof(ORIGIN_OPTIONS) / sizeof(ORIGIN_OPTIONS[0]);
static const char *const SENSOR_UI_NAMES[NUM_SENSORS] = {
    "TGS822",  "MQ135",   "MQ3", "TGS2611", "TGS2620",
    "TGS2600", "TGS2602", "MQ8", "TGS813",  "TGS816"};

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
  nextion.begin(NEXTION_BAUD);
  // We use our own ASCII EVT:* protocol. Suppress command ACK/error packets so
  // binary Nextion return frames never share the event stream.
  nextion.command("bkcmd=0");
  nextionBootMs = millis();

  Serial.println(
      F("{\"nextion\":{\"port\":\"Serial2\",\"baud\":9600,\"mcu_rx\":\"PH0/RXD2 pin 8\",\"mcu_tx\":\"PH1/TXD2 pin 9\",\"mega_header_rx\":17,\"mega_header_tx\":16}}"));

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
  if (sensorsReady && sensors.allAdcAvailable()) {
    sensors.calibrate();
    calibrationReady = sensors.loadCalibration();
  }
#else
  if (sensorsReady) {
    calibrationReady = sensors.loadCalibration();
  }
  if (sensorsReady && !calibrationReady) {
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

void startAcquisition(AcquisitionMode mode) {
  acqMode = mode;
  acqCycle = 1;
  acqSampleIdx = 0;
  acqTotalSamples = 0;
  inference.reset();

  acqState = AcqState::PURGING;
  acqPhaseStartMs = millis();
  setActuators();

  // Event: ACQ_START
  //
  // Metadata ini membuat laptop dapat menjadi passive listener: operator
  // memilih roast/origin/batch dan menekan START di Nextion, lalu host dapat
  // menyimpan CSV tanpa prompt/command manual.
  char takeFilename[40] = {};
  buildTakeFilename(takeFilename, sizeof(takeFilename), true);
  const char roastCode =
      roastSelection == 0 ? 'L' : (roastSelection == 1 ? 'M' : 'D');
  const char *roastLevel =
      roastSelection == 0 ? "light"
                          : (roastSelection == 1 ? "medium" : "dark");

  Serial.print(F("{\"event\":\"ACQ_START\",\"mode\":\""));
  Serial.print(mode == AcquisitionMode::AI_TEST ? F("ai_test") : F("labeled_data"));
  Serial.print(F("\",\"phase\":\"purging\",\"cycle\":1"));
  Serial.print(F(",\"source\":\"nextion_or_serial\""));
  Serial.print(F(",\"sample_id\":\""));
  Serial.print(roastCode);
  Serial.print('-');
  Serial.print(ORIGIN_OPTIONS[originSelection]);
  Serial.print(F("\",\"roast_level\":\""));
  Serial.print(roastLevel);
  Serial.print(F("\",\"origin_code\":\""));
  Serial.print(ORIGIN_OPTIONS[originSelection]);
  Serial.print(F("\",\"batch_id\":\"B"));
  if (batchNumber < 10) {
    Serial.print('0');
  }
  Serial.print(batchNumber);
  Serial.print(F("\",\"filename\":\""));
  Serial.print(takeFilename);
  Serial.print('"');
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
  acqStateBeforePause = AcqState::IDLE;
  acqPausedElapsedMs = 0;
  acqMode = AcquisitionMode::NONE;
  setActuators();
  Serial.println(F("{\"event\":\"ACQ_STOP\",\"phase\":\"idle\"}"));
}

void pauseAcquisition() {
  if (acqState != AcqState::COLLECTING && acqState != AcqState::PURGING) {
    return;
  }
  acqStateBeforePause = acqState;
  acqPausedElapsedMs = millis() - acqPhaseStartMs;
  acqState = AcqState::PAUSED;
  setActuators();
  Serial.println(F("{\"event\":\"ACQ_PAUSE\",\"phase\":\"paused\"}"));
}

void resumeAcquisition() {
  if (acqState != AcqState::PAUSED ||
      (acqStateBeforePause != AcqState::PURGING &&
       acqStateBeforePause != AcqState::COLLECTING)) {
    return;
  }
  acqState = acqStateBeforePause;
  acqPhaseStartMs = millis() - acqPausedElapsedMs;
  acqPausedElapsedMs = 0;
  setActuators();
  Serial.print(F("{\"event\":\"ACQ_RESUME\",\"phase\":\""));
  Serial.print(acqStateName());
  Serial.println(F("\"}"));
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
        // Semua siklus (Purging + Collecting) selesai -> COMPLETE.
        acqState = AcqState::COMPLETE;
        setActuators();
        printAcquisitionSummary();
        if (acqMode == AcquisitionMode::AI_TEST) {
          if (strcmp(nextionPageName, "pTestRun") == 0) {
            nextion.progress("jAI", 100);
            nextion.text("tStep1", "DONE");
            nextion.text("tStep2", "DONE");
            nextion.text("tStep3", "DONE");
            nextion.text("tStep4", "RUNNING");
            nextion.text("tEta", "EST. REMAINING 00:00");
          }
          doInference();
          showNextionPage("pResult");
          updateNextionInferenceResult();
          char history[UI_HISTORY_TEXT_CAPACITY] = {};
          snprintf(history, sizeof(history), "T-%04u  %s  LOCAL", testSequence,
                   inference.predictLabel());
          addUiHistory(history);
          ++testSequence;
        } else {
          showNextionPage("pDataDone");
          char filename[40] = {};
          char completed[32] = {};
          char history[UI_HISTORY_TEXT_CAPACITY] = {};
          buildTakeFilename(filename, sizeof(filename), true);
          snprintf(completed, sizeof(completed), "%u/%u CYCLES COMPLETE",
                   ACQ_REPETITIONS, ACQ_REPETITIONS);
          nextion.text("tFile", filename);
          nextion.text("tDone", completed);
          snprintf(history, sizeof(history), "%s  %u CYCLES", filename,
                   ACQ_REPETITIONS);
          addUiHistory(history);
        }
        acqState = AcqState::IDLE;
        acqStateBeforePause = AcqState::IDLE;
        acqMode = AcquisitionMode::NONE;
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
  delay(200); // beri Nextion waktu load halaman sebelum update komponen (9600 baud)
  if (strcmp(pageName, "pSplash") != 0) {
    nextionHomeSent = true;
  }
  strncpy(nextionPageName, pageName, sizeof(nextionPageName) - 1);
  nextionPageName[sizeof(nextionPageName) - 1] = '\0';
  if (strcmp(pageName, "pDataRun") == 0) {
    nextionSensorIndex = 0;
  } else if (strcmp(pageName, "pTake") == 0) {
    updateNextionTakePage();
  } else if (strcmp(pageName, "pTest") == 0) {
    updateNextionTestPage();
  } else if (strcmp(pageName, "pHistory") == 0) {
    updateNextionHistoryPage();
  } else if (strcmp(pageName, "pSettings") == 0) {
    updateNextionSettingsPage();
  } else if (strcmp(pageName, "pTestRun") == 0) {
    updateNextionTestRunPage();
  } else if (strcmp(pageName, "pCal") == 0) {
    updateNextionCalibrationPage();
  } else if (strcmp(pageName, "pResult") == 0) {
    updateNextionInferenceResult();
  }
}

void updateNextionTakePage() {
  char batch[12] = {};
  char cycles[12] = {};
  char filename[40] = {};
  snprintf(batch, sizeof(batch), "B%02u", batchNumber);
  snprintf(cycles, sizeof(cycles), "%u", ACQ_REPETITIONS);
  buildTakeFilename(filename, sizeof(filename), true);
  nextion.text("tRoast", ROAST_OPTIONS[roastSelection]);
  nextion.text("tOrigin", ORIGIN_OPTIONS[originSelection]);
  nextion.text("tBatch", batch);
  nextion.text("tCycles", cycles);
  nextion.text("tFile", filename);

  const bool ready = ROAST_OPTIONS[roastSelection][0] != '\0' &&
                     ORIGIN_OPTIONS[originSelection][0] != '\0' &&
                     batchNumber > 0 && ACQ_REPETITIONS > 0 &&
                     filename[0] != '\0';

  nextion.text("tStat", ready ? "Siap untuk pengambilan data"
                              : "Data belum lengkap");
  nextion.textColor("tStat",
                    ready ? NEXTION_STATUS_GREEN : NEXTION_STATUS_RED);
  nextion.touch("mStart", ready);
}

void buildTakeFilename(char *buffer, size_t size, bool withExtension) {
  if (buffer == nullptr || size == 0) {
    return;
  }
  const char roastCode = roastSelection == 0 ? 'L' : (roastSelection == 1 ? 'M' : 'D');
  snprintf(buffer, size, withExtension ? "%c-%s_B%02u.csv" : "%c-%s_B%02u",
           roastCode, ORIGIN_OPTIONS[originSelection], batchNumber);
}

void updateNextionTestPage() {
  const bool arrayReady = sensorsReady && sensors.allAdcAvailable();
  char testId[24] = {};
  snprintf(testId, sizeof(testId), "AUTO - T%04u", testSequence);
  nextion.text("tTestId", testId);
  nextion.text("tMode", "LOCAL INFERENCE");
  nextion.text("tAtmega", arrayReady ? "READY" : "ERROR");
  nextion.text("tPi", "LOCAL READY");
  nextion.text("tSensors", arrayReady ? "10/10 SENSOR" : "ADC ERROR");
}

void updateNextionHistoryPage() {
  static const char *const fields[UI_HISTORY_CAPACITY] = {
      "tH0", "tH1", "tH2", "tH3"};
  for (uint8_t i = 0; i < UI_HISTORY_CAPACITY; ++i) {
    nextion.text(fields[i], i < uiHistoryCount ? uiHistory[i] : "-");
  }
}

void updateNextionSettingsPage() {
  char duration[24] = {};
  snprintf(duration, sizeof(duration), "%us / %us", ACQ_PURGE_SECONDS,
           ACQ_COLLECTION_SECONDS);
  nextion.text("tWifi", "N/A");
  nextion.text("tDuration", duration);
  nextion.text("tBright", "80 %");
  nextion.text("tLang", "EN / ID");
  nextion.text("tDevId", "ATMEGA2560");
  nextion.text("tFw", "v1.10");
}

void updateNextionTestRunPage() {
  char testId[24] = {};
  snprintf(testId, sizeof(testId), "TEST T-%04u", testSequence);
  nextion.text("tTestId", testId);
  nextion.text("tPi", "LOCAL");
  nextion.progress("jAI", 0);
  nextion.text("tStep1", "RUNNING");
  nextion.text("tStep2", "WAIT");
  nextion.text("tStep3", "WAIT");
  nextion.text("tStep4", "LOCAL");
  nextion.text("tEta", "EST. REMAINING --:--");
}

void updateNextionTestRunStatus() {
  if (strcmp(nextionPageName, "pTestRun") != 0 ||
      acqMode != AcquisitionMode::AI_TEST) {
    return;
  }

  const uint32_t phaseElapsedMs =
      acqState == AcqState::PAUSED ? acqPausedElapsedMs
                                   : millis() - acqPhaseStartMs;
  const uint32_t phaseElapsed = phaseElapsedMs / 1000UL;
  const uint32_t cycleSeconds = ACQ_PURGE_SECONDS + ACQ_COLLECTION_SECONDS;
  const uint32_t completedCycles = acqCycle > 0 ? acqCycle - 1 : 0;
  uint32_t currentCycleElapsed = 0;

  AcqState effectiveState =
      acqState == AcqState::PAUSED ? acqStateBeforePause : acqState;
  if (effectiveState == AcqState::PURGING) {
    currentCycleElapsed =
        phaseElapsed < ACQ_PURGE_SECONDS ? phaseElapsed : ACQ_PURGE_SECONDS;
  } else if (effectiveState == AcqState::COLLECTING) {
    const uint32_t collectElapsed =
        phaseElapsed < ACQ_COLLECTION_SECONDS ? phaseElapsed
                                               : ACQ_COLLECTION_SECONDS;
    currentCycleElapsed = ACQ_PURGE_SECONDS + collectElapsed;
  }

  const uint32_t totalSeconds = cycleSeconds * ACQ_REPETITIONS;
  uint32_t doneSeconds = completedCycles * cycleSeconds + currentCycleElapsed;
  if (doneSeconds > totalSeconds) {
    doneSeconds = totalSeconds;
  }
  const uint32_t remaining = totalSeconds - doneSeconds;
  const uint8_t percent = totalSeconds == 0
                              ? 0
                              : static_cast<uint8_t>(
                                    (doneSeconds * 100UL) / totalSeconds);

  nextion.progress("jAI", percent);
  if (acqState == AcqState::PAUSED) {
    nextion.text("tStep1", "PAUSED");
    nextion.text("tStep2", "PAUSED");
  } else if (effectiveState == AcqState::PURGING) {
    nextion.text("tStep1", "RUNNING");
    nextion.text("tStep2", "WAIT");
  } else if (effectiveState == AcqState::COLLECTING) {
    nextion.text("tStep1", "DONE");
    nextion.text("tStep2", "RUNNING");
  }
  nextion.text("tStep3", "WAIT");
  nextion.text("tStep4", "LOCAL");

  char eta[28] = {};
  snprintf(eta, sizeof(eta), "EST. REMAINING %02lu:%02lu",
           static_cast<unsigned long>(remaining / 60UL),
           static_cast<unsigned long>(remaining % 60UL));
  nextion.text("tEta", eta);
}

void updateNextionCalibrationPage() {
  const bool arrayReady = sensorsReady && sensors.allAdcAvailable();
  nextion.text("tSensors", arrayReady ? "10/10 OK" : "ADC ERROR");
  nextion.text("tPump", "STOPPED");
  nextion.text("tChamber", arrayReady ? "READY" : "CHECK ADC");
  nextion.text("tBase", calibrationReady ? "Stable" : "NOT SET");
}

void addUiHistory(const char *entry) {
  if (entry == nullptr || entry[0] == '\0') {
    return;
  }
  for (int8_t i = UI_HISTORY_CAPACITY - 1; i > 0; --i) {
    strncpy(uiHistory[i], uiHistory[i - 1], UI_HISTORY_TEXT_CAPACITY - 1);
    uiHistory[i][UI_HISTORY_TEXT_CAPACITY - 1] = '\0';
  }
  strncpy(uiHistory[0], entry, UI_HISTORY_TEXT_CAPACITY - 1);
  uiHistory[0][UI_HISTORY_TEXT_CAPACITY - 1] = '\0';
  if (uiHistoryCount < UI_HISTORY_CAPACITY) {
    ++uiHistoryCount;
  }
}

void exportUiHistory() {
  Serial.println(F("{\"event\":\"HISTORY_EXPORT_BEGIN\"}"));
  for (uint8_t i = 0; i < uiHistoryCount; ++i) {
    Serial.print(F("{\"history_index\":"));
    Serial.print(i);
    Serial.print(F(",\"value\":\""));
    Serial.print(uiHistory[i]);
    Serial.println(F("\"}"));
  }
  Serial.println(F("{\"event\":\"HISTORY_EXPORT_END\"}"));
}

void resetUiSettings() {
  roastSelection = 0;
  originSelection = 0;
  batchNumber = 32;
  nextion.command("dim=80");
}

void sendNextionAlert(const char *title, const char *message,
                      const char *action) {
  showNextionPage("pAlert");
  nextion.text("tAlert", title);
  nextion.text("tMsg", message);
  nextion.text("tAction", action);
}

void updateNextionRunStatus() {
  if (strcmp(nextionPageName, "pDataRun") != 0) {
    return;
  }

  char text[32] = {};
  const uint32_t cycle = acqCycle == 0 ? 1 : acqCycle;
  const AcqState effectiveState =
      acqState == AcqState::PAUSED ? acqStateBeforePause : acqState;
  const uint32_t totalSeconds = effectiveState == AcqState::PURGING
                                    ? ACQ_PURGE_SECONDS
                                    : ACQ_COLLECTION_SECONDS;
  const uint32_t elapsedSeconds =
      (acqState == AcqState::PAUSED ? acqPausedElapsedMs
                                    : millis() - acqPhaseStartMs) /
      1000UL;
  const uint32_t remaining =
      elapsedSeconds < totalSeconds ? totalSeconds - elapsedSeconds : 0;
  const uint32_t cycleSeconds = ACQ_PURGE_SECONDS + ACQ_COLLECTION_SECONDS;
  const uint32_t completedCycles = cycle > 0 ? cycle - 1 : 0;
  uint32_t currentCycleSeconds = 0;
  if (effectiveState == AcqState::PURGING) {
    currentCycleSeconds =
        elapsedSeconds < ACQ_PURGE_SECONDS ? elapsedSeconds : ACQ_PURGE_SECONDS;
  } else if (effectiveState == AcqState::COLLECTING) {
    const uint32_t collectSeconds =
        elapsedSeconds < ACQ_COLLECTION_SECONDS ? elapsedSeconds
                                                 : ACQ_COLLECTION_SECONDS;
    currentCycleSeconds = ACQ_PURGE_SECONDS + collectSeconds;
  }
  const uint32_t totalRunSeconds = cycleSeconds * ACQ_REPETITIONS;
  const uint32_t completedRunSeconds =
      completedCycles * cycleSeconds + currentCycleSeconds;
  const uint8_t cyclePercent =
      totalRunSeconds == 0
          ? 0
          : static_cast<uint8_t>(
                (completedRunSeconds * 100UL) / totalRunSeconds);

  buildTakeFilename(text, sizeof(text), false);
  nextion.text("tSample", text);
  snprintf(text, sizeof(text), "CYCLE %lu / %u", (unsigned long)cycle,
           ACQ_REPETITIONS);
  nextion.text("tCycle", text);
  nextion.progress("jCycle", cyclePercent > 100 ? 100 : cyclePercent);
  nextion.text("tPhase", acqStateName());
  snprintf(text, sizeof(text), "%02lu:%02lu", (unsigned long)(remaining / 60),
           (unsigned long)(remaining % 60));
  nextion.text("tRemain", text);
  if (sensors.environmentValid()) {
    // AVR-libc printf/snprintf tidak mengaktifkan formatter %f secara default.
    // Menggunakan %.1f di ATmega2560 dapat menghasilkan "?" di Nextion walau
    // nilai SHT30 valid. dtostrf() adalah formatter float yang aman di AVR.
    char value[16] = {};
    dtostrf(sensors.getTemperatureC(), 0, 1, value);
    snprintf(text, sizeof(text), "%s C", value);
    nextion.text("tTemp", text);
    dtostrf(sensors.getHumidityRh(), 0, 1, value);
    snprintf(text, sizeof(text), "%s %%RH", value);
    nextion.text("tHum", text);
  } else {
    nextion.text("tTemp", "N/A");
    nextion.text("tHum", "N/A");
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
  nextion.text("tSensors", text);
  nextionSensorIndex = (index + 1) % NUM_SENSORS;
}

void updateNextionInferenceResult() {
  const char *label = inference.predictLabel();
  const bool resultReady = label != nullptr && strcmp(label, "N/A") != 0;
  const char *displayLabel = label;
  if (resultReady) {
    if (strcmp(label, "light") == 0) {
      displayLabel = "LIGHT";
    } else if (strcmp(label, "medium") == 0) {
      displayLabel = "MEDIUM";
    } else if (strcmp(label, "dark") == 0) {
      displayLabel = "DARK";
    }
  }

  nextion.text("tRoast", resultReady ? displayLabel : "N/A");
  nextion.text("tRConf", "N/A");
  nextion.text("tOrigin", "N/A");
  nextion.text("tOConf", "N/A");
  nextion.progress("jLight", 0);
  nextion.progress("jMedium", 0);
  nextion.progress("jDark", 0);
}

void handleNextionEvent(const char *event) {
  if (event == nullptr || strncmp(event, "EVT:", 4) != 0) {
    return;
  }

  Serial.print(F("{\"nextion_event\":\""));
  Serial.print(event);
  Serial.println(F("\"}"));

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
  } else if (strcmp(event, "EVT:SETTINGS") == 0) {
    showNextionPage("pSettings");
  } else if (strcmp(event, "EVT:ROAST_NEXT") == 0) {
    roastSelection = (roastSelection + 1) % ROAST_OPTION_COUNT;
    updateNextionTakePage();
  } else if (strcmp(event, "EVT:ROAST_PREV") == 0) {
    roastSelection = roastSelection == 0 ? ROAST_OPTION_COUNT - 1
                                         : roastSelection - 1;
    updateNextionTakePage();
  } else if (strcmp(event, "EVT:ORIGIN_NEXT") == 0) {
    originSelection = (originSelection + 1) % ORIGIN_OPTION_COUNT;
    updateNextionTakePage();
  } else if (strcmp(event, "EVT:ORIGIN_PREV") == 0) {
    originSelection = originSelection == 0 ? ORIGIN_OPTION_COUNT - 1
                                           : originSelection - 1;
    updateNextionTakePage();
  } else if (strcmp(event, "EVT:BATCH_INC") == 0) {
    if (batchNumber < 9999) {
      ++batchNumber;
    }
    updateNextionTakePage();
  } else if (strcmp(event, "EVT:BATCH_DEC") == 0) {
    if (batchNumber > 1) {
      --batchNumber;
    }
    updateNextionTakePage();
  } else if (strcmp(event, "EVT:DATA_START") == 0) {
    if (acqState == AcqState::PAUSED) {
      resumeAcquisition();
    } else if (acqState == AcqState::IDLE && sensorsReady &&
               sensors.allAdcAvailable()) {
      startAcquisition();
      showNextionPage("pDataRun");
    } else if (!sensorsReady || !sensors.allAdcAvailable()) {
      sendNextionAlert("Sensor error", "ADC belum siap",
                       "Periksa I2C lalu retry");
    } else {
      sendNextionAlert("Acquisition aktif", "Run sedang berjalan",
                       "Gunakan pause/cancel");
    }
  } else if (strcmp(event, "EVT:DATA_PAUSE") == 0) {
    if (acqState == AcqState::PAUSED) {
      resumeAcquisition();
    } else {
      pauseAcquisition();
    }
    updateNextionRunStatus();
  } else if (strcmp(event, "EVT:DATA_CANCEL") == 0) {
    stopAcquisition();
    showNextionPage("pHome");
  } else if (strcmp(event, "EVT:NEW_BATCH") == 0) {
    if (batchNumber < 9999) {
      ++batchNumber;
    }
    showNextionPage("pTake");
  } else if (strcmp(event, "EVT:CAL_START") == 0) {
    if (strcmp(nextionPageName, "pCal") != 0) {
      showNextionPage("pCal");
    } else if (!sensorsReady || !sensors.allAdcAvailable()) {
      sendNextionAlert("Calibration error", "ADC belum siap",
                       "Periksa I2C lalu retry");
    } else if (acqState != AcqState::IDLE) {
      sendNextionAlert("Calibration busy", "Akuisisi sedang berjalan",
                       "Cancel run lebih dulu");
    } else {
      actuator.stop();
      nextion.text("tBase", "RUNNING");
      sensors.calibrate();
      calibrationReady = sensors.loadCalibration();
      updateNextionCalibrationPage();
      Serial.print(F("{\"event\":\"CALIBRATION_COMPLETE\",\"ok\":"));
      Serial.print(calibrationReady ? F("true") : F("false"));
      Serial.println(F("}"));
    }
  } else if (strcmp(event, "EVT:AI_START") == 0) {
    if (!sensorsReady || !sensors.allAdcAvailable()) {
      sendNextionAlert("Sensor error", "ADC belum siap",
                       "Periksa I2C lalu retry");
    } else if (acqState != AcqState::IDLE) {
      sendNextionAlert("Acquisition aktif", "Run sedang berjalan",
                       "Cancel run lebih dulu");
    } else {
      startAcquisition(AcquisitionMode::AI_TEST);
      showNextionPage("pTestRun");
      updateNextionTestRunStatus();
    }
  } else if (strcmp(event, "EVT:AI_CANCEL") == 0) {
    if (acqState != AcqState::IDLE) {
      stopAcquisition();
    }
    showNextionPage("pHome");
  } else if (strcmp(event, "EVT:RESULT_SAVE") == 0) {
    Serial.print(F("{\"event\":\"RESULT_EXPORT\",\"roast\":\""));
    Serial.print(inference.predictLabel());
    Serial.println(F("\",\"origin\":null,\"confidence\":null}"));
    sendNextionAlert("Result exported", "Hasil dikirim ke Serial USB",
                     "History RAM tetap tersimpan");
  } else if (strcmp(event, "EVT:HISTORY_CLEAR") == 0 ||
             strcmp(event, "EVT:HISTORY_EXPORT") == 0) {
    exportUiHistory();
    updateNextionHistoryPage();
  } else if (strcmp(event, "EVT:RESET") == 0) {
    resetUiSettings();
    updateNextionSettingsPage();
    Serial.println(F("{\"event\":\"UI_SETTINGS_RESET\"}"));
  } else if (strcmp(event, "EVT:RETRY") == 0) {
    showNextionPage("pHome");
  } else if (strcmp(event, "EVT:EXIT") == 0) {
    stopAcquisition();
    sendNextionAlert("System active", "Power off dilakukan manual",
                     "Hardware tetap aman");
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
  updateNextionTestRunStatus();
}
