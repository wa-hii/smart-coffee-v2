
// ═════════════════════════════════════════════════════════════════════════════
// Smart Coffee E-NOSE v2 — Program Utama (ATmega 2560)
//
// Portable Embedded AI untuk Standarisasi Roasting Kopi
// Klasifikasi: Light / Medium / Dark Roast
//
// Alur akuisisi aktif per sampel:
//   PURGING (valve OFF/udara bersih, 25 s)
//     → COLLECTING (valve ON/aroma kopi, 5 s)
//     → Take Data dan AI Test sama-sama 30 siklus (900 ADC samples)
//   Setelah mode AI_TEST selesai → default firmware: N/A.
//   Standalone bench profile: 30-feature SVM entirely on ATmega2560.
//
// Arsitektur modular:
//   sensor.h/cpp    — ADS1115, MQ, TGS sensors + kalibrasi EEPROM
//   actuator.h/cpp  — valve + pump PWM control
//   inference.h/cpp — feature accumulation + Random Forest classifier
//   main.cpp        — state machine, serial commands, coordinator
// ═════════════════════════════════════════════════════════════════════════════
#include "TaskScheduler.h"
#include "ai_rf30_return.h"
#include "acquisition_timing.h"
#include "actuator.h"
#include "inference.h"
#include "nextion_transport.h"
#include "sensor.h"
#ifndef SMART_COFFEE_STANDALONE_SVM30
#define SMART_COFFEE_STANDALONE_SVM30 0
#endif
#if SMART_COFFEE_STANDALONE_SVM30
#include "embedded_svm30_features.h"
#include "embedded_svm30_classifier.h"
#endif
#include <Arduino.h>
#include <Wire.h>
#include <stdio.h>
#include <string.h>

// ─── Konfigurasi Akuisisi
// ─────────────────────────────────────────────────────
#define ACQ_COLLECTION_SECONDS 5 // durasi menghirup aroma kopi (detik)
#define ACQ_PURGE_SECONDS 25     // durasi purging ke udara bebas (detik)
#define ACQ_DATA_REPETITIONS 30  // Nextion Take Data
#define ACQ_AI_REPETITIONS ACQ_DATA_REPETITIONS // AI Test identik dengan Take Data
#define ACQ_REPETITIONS (acqMode == AcquisitionMode::LABELED_DATA ? ACQ_DATA_REPETITIONS : ACQ_AI_REPETITIONS)
#define BASELINE_SAMPLES 60      // 60 samples, 1 Hz, clean-air ADC reference

// Identitas source BUILD, bukan bukti firmware sudah di-flash. Sertakan
// pada ACQ_START supaya host tetap dapat mengidentifikasi firmware saat
// FW_HELLO boot tidak tertangkap karena pembukaan port USB/DTR.
#if SMART_COFFEE_STANDALONE_SVM30
#define SMART_COFFEE_BUILD_ID "standalone-svm30-bench-20261111"
#else
#define SMART_COFFEE_BUILD_ID "take30-ai30-rfhost-20261110"
#endif

// ─── Feature Flags
// ────────────────────────────────────────────────────────────
#ifndef IS_CALIBRATING_GAS_SENSOR
#define IS_CALIBRATING_GAS_SENSOR 0 // 1 hanya untuk prosedur kalibrasi terawasi
#endif

// Penggerakan valve melalui USB hanya untuk bench test ber-SOP, tidak aktif
// pada firmware normal.
#ifndef ENABLE_MANUAL_ACTUATOR_TESTS
#define ENABLE_MANUAL_ACTUATOR_TESTS 0
#endif

// The RF500 model has not passed prospective/device-independent release QA.
// This remains OFF on all normal firmware builds. Only an approved, supervised
// test may build with -DENABLE_PI_RF30_RETURN=1.
#ifndef ENABLE_PI_RF30_RETURN
#define ENABLE_PI_RF30_RETURN 0
#endif
#if SMART_COFFEE_STANDALONE_SVM30
#if !defined(ENABLE_AVR_SVM30) || !ENABLE_AVR_SVM30
#error "Standalone profile requires embedded SVM30 classifier enabled"
#endif
#if ENABLE_PI_RF30_RETURN || ENABLE_MANUAL_ACTUATOR_TESTS || USE_ON_DEVICE_INFERENCE
#error "Standalone SVM mode cannot enable Pi reply, manual actuators or legacy RF"
#endif
#endif
static constexpr uint32_t AI_RF30_REPLY_TIMEOUT_MS = 30000UL;

// ─── Task Scheduler Intervals
// ─────────────────────────────────────────────────
#define TASK_INTERVAL_MS_ADS 1000   // 1 sampel/detik
#define TASK_INTERVAL_MS_SERIAL 100 // polling Serial 10×/detik
#define TASK_INTERVAL_MS_UI 125 // 8 slots x 125ms = one UI refresh/second
#define NEXTION_BAUD 9600UL         // harus sama dengan baud project HMI aktif

// Timing slippage >=1s means one full ADC sampling interval was missed.
// Quarantine rather than publish a misleading "15-minute" complete CSV.
static constexpr uint32_t ACQ_MAX_PHASE_LATENESS_MS = 1000UL;

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
#if SMART_COFFEE_STANDALONE_SVM30
// The standalone backup never buffers 900 samples or a CSV in MCU RAM.
EmbeddedSvm30::Features svm30Capture;
// A pre-inference guard, not a replacement for B5 stack watermark testing
// on the actual 16 MHz MCU. Leave room for kernel[125], scaled[30], math
// library calls, scheduler and Nextion.
extern "C" char __heap_start;
extern "C" char *__brkval;
static int16_t standaloneFreeRam() {
  char top;
  return &top - (__brkval ? __brkval : &__heap_start);
}
#endif
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
uint32_t acqStartMs = 0;
uint32_t acqPauseStartMs = 0;
uint32_t acqPausedTotalMs = 0;
uint32_t aiRf30SessionToken = 0;
uint32_t aiRf30SessionSequence = 0;
uint32_t aiRf30Deadline = 0;
bool aiRf30Pending = false;
AiRf30Return::Roast aiRf30Roast = AiRf30Return::Roast::NONE;
bool baselineCaptureActive = false;
uint16_t baselineSampleIdx = 0;

// ─── Buffer Command Serial
// ────────────────────────────────────────────────────
char cmdBuf[64] = {};
int cmdBufIdx = 0;

// ─── Forward Declarations
// ─────────────────────────────────────────────────────
void adsCallback();
void serialCallback();
void uiCallback();
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
void stopBaselineCapture(const char *reason);
void updateNextionRunStatus();
void updateNextionSensorSnapshot();
void updateNextionInferenceResult();
void buildTakeFilename(char *buffer, size_t size, bool withExtension = true);
void restoreNextionPageAfterBoot();
void pauseAcquisition();
void resumeAcquisition();
void sendNextionAlert(const char *title, const char *message,
                      const char *action);
void addUiHistory(const char *entry);
void exportUiHistory();
void resetUiSettings();
void processAiRf30Reply(const char *cmd);
void expireAiRf30Reply();

// ─── TaskScheduler Tasks
// ──────────────────────────────────────────────────────
Task taskAds(TASK_INTERVAL_MS_ADS, TASK_FOREVER, &adsCallback);
Task taskSerial(TASK_INTERVAL_MS_SERIAL, TASK_FOREVER, &serialCallback);
Task taskUi(TASK_INTERVAL_MS_UI, TASK_FOREVER, &uiCallback);

// ─── Status sensor
// ────────────────────────────────────────────────────────────
bool sensorsReady = false;
bool calibrationReady = false;
bool nextionHomeSent = false;
uint32_t nextionBootMs = 0;
char nextionPageName[16] = "pSplash";
uint8_t nextionSensorIndex = 0;
uint8_t nextionRunUiSlot = 0;
uint8_t roastSelection = 0;
uint8_t originSelection = 0;
// Baseline akuisisi aktif dimulai dari B32. NEXT/BATCH +/- tetap dapat
// digunakan untuk batch berikutnya.
uint16_t batchNumber = 32;
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
  // Build identity is a self-reported protocol marker, NOT a verified
  // read-back of the binary installed in the remote custom PCB. Correlate
  // with the ACQ_START marker during supervised validation; ISP verification
  // is still required for exact chip/flash identity.
  Serial.print(F("{\"event\":\"FW_HELLO\",\"protocol\":\"legacy-json.v1\",\"build_id\":\""));
  Serial.print(F(SMART_COFFEE_BUILD_ID));
  Serial.print(F("\",\"adc_channels\":10,\"data_cycles_total\":"));
  Serial.print(ACQ_DATA_REPETITIONS);
  Serial.print(F(",\"ai_cycles_total\":"));
  Serial.print(ACQ_AI_REPETITIONS);
  Serial.println(F(",\"purge_s\":25,\"collect_s\":5}"));
  nextion.begin(NEXTION_BAUD);
  // We use our own ASCII EVT:* protocol. Suppress command ACK/error packets so
  // binary Nextion return frames never share the event stream.
  nextion.command("bkcmd=0");
  nextionBootMs = millis();

  Serial.println(
      F("{\"nextion\":{\"port\":\"Serial2\",\"baud\":9600,\"mcu_rx\":\"PH0/RXD2 TQFP pin 12\",\"mcu_tx\":\"PH1/TXD2 TQFP pin 13\",\"mega_header_rx\":17,\"mega_header_tx\":16}}"));

  actuator.begin();

  // The RF30 Pi-return build also needs a bounded boot before the Nextion
  // scheduler can advance pSplash -> pHome. Do not scan all 126 I2C
  // addresses on startup of these supervised profiles: a faulty I2C
  // device/wire can otherwise leave the HMI indefinitely initializing.
  // Keep the legacy default startup behavior unchanged.
#if SMART_COFFEE_STANDALONE_SVM30 || ENABLE_PI_RF30_RETURN
  Wire.begin();
  Wire.setWireTimeout(25000UL, true);
#else
  // Diagnostik: scan I2C bus terlebih dahulu
  scanI2C();
#endif

  // Init sensor — TIDAK fatal jika gagal (untuk debugging)
  sensorsReady = sensors.begin();
  if (!sensorsReady) {
    Serial.println(F("{\"warn\":\"Sensor init gagal. Periksa wiring "
                     "(SDA=pin20, SCL=pin21).\"}"));
    Serial.println(F("{\"warn\":\"Kirim #scan; untuk scan ulang I2C bus.\"}"));
  }

#if IS_CALIBRATING_GAS_SENSOR
  if (sensorsReady && sensors.allAdcAvailable()) {
    calibrationReady = sensors.calibrate();
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
  scheduler.addTask(taskUi);
  taskAds.enable();
  taskSerial.enable();
  taskUi.enable();

  printWelcome();
}

// ═══════════════════════════════════════════════════════════════════════════════
//  loop()
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
  // Resolve deadlines independently from the one-second ADC callback and
  // independently from best-effort Nextion/USB command throughput.
  processAcquisitionState();
  scheduler.execute();
  processAcquisitionState();
  expireAiRf30Reply();
}

// ═══════════════════════════════════════════════════════════════════════════════
//  printWelcome() — Welcome banner
// ═══════════════════════════════════════════════════════════════════════════════
void printWelcome() {
#if !SMART_COFFEE_STANDALONE_SVM30
  Serial.println();
  Serial.println(F("=============================================="));
  Serial.println(F("  Smart Coffee E-NOSE v2 - ATmega 2560"));
  Serial.println(F("=============================================="));
  Serial.println(F("  Perintah:"));
  Serial.println(F("    #start;       Mulai akuisisi data sensor"));
  Serial.println(F("    #stop;        Hentikan akuisisi"));
  Serial.println(F("    #scan;        Scan I2C bus"));
#if ENABLE_MANUAL_ACTUATOR_TESTS
  Serial.println(F("    #valve_on; / #valve_off; / #valve_test; (SOP bench)"));
#else
  Serial.println(F("    Manual valve test disabled; SOP bench diperlukan"));
#endif
  Serial.println(F("    #help;        Tampilkan bantuan"));
  Serial.println(F("=============================================="));
  Serial.println(
      F("{\"info\":\"Sistem siap. Kirim #start; untuk mulai akuisisi.\"}"));
#endif
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ACQUISITION STATE MACHINE
// ═══════════════════════════════════════════════════════════════════════════════

void startAcquisition(AcquisitionMode mode) {
  // Any new data/AI acquisition invalidates the previous return token.
  aiRf30Pending = false;
  aiRf30Roast = AiRf30Return::Roast::NONE;
  aiRf30SessionToken = 0;
  acqMode = mode;
  acqCycle = 1;
  acqSampleIdx = 0;
  acqTotalSamples = 0;
  acqStartMs = millis();
  acqPauseStartMs = 0;
  acqPausedTotalMs = 0;
  inference.reset();
#if SMART_COFFEE_STANDALONE_SVM30
  svm30Capture.reset();
#endif
  if (mode == AcquisitionMode::AI_TEST) {
    ++aiRf30SessionSequence;
    aiRf30SessionToken =
        (static_cast<uint32_t>(millis()) ^
         (aiRf30SessionSequence * 2654435761UL) ^ 0xB1F503A9UL);
    if (aiRf30SessionToken == 0) aiRf30SessionToken = 1;
  }

  acqState = AcqState::PURGING;
  acqPhaseStartMs = millis();
  setActuators();

  // Event: ACQ_START
#if !SMART_COFFEE_STANDALONE_SVM30
  //
  // Metadata ini membuat laptop dapat menjadi passive listener: operator
  // memilih roast/origin/batch dan menekan START di Nextion, lalu host dapat
  // menyimpan CSV tanpa prompt/command manual.
  Serial.print(F("{\"event\":\"ACQ_START\",\"mode\":\""));
  Serial.print(mode == AcquisitionMode::AI_TEST ? F("ai_test") : F("labeled_data"));
  Serial.print(F("\",\"phase\":\"purging\",\"cycle\":1"));
  Serial.print(F(",\"source\":\"nextion_or_serial\""));
  Serial.print(F(",\"fw_build_id\":\""));
  Serial.print(F(SMART_COFFEE_BUILD_ID));
  Serial.print('"');
  if (mode == AcquisitionMode::AI_TEST) {
    char token[9] = {};
    AiRf30Return::tokenHex(aiRf30SessionToken, token, sizeof(token));
    Serial.print(F(",\"ai_session_token\":\""));
    Serial.print(token);
    Serial.print('"');
  }
  // Label pTake hanya untuk labeled_data, bukan jawaban kopi pada AI_TEST.
  if (mode == AcquisitionMode::LABELED_DATA) {
    char takeFilename[40] = {};
    buildTakeFilename(takeFilename, sizeof(takeFilename), true);
    const char roastCode =
        roastSelection == 0 ? 'L' : (roastSelection == 1 ? 'M' : 'D');
    const char *roastLevel =
        roastSelection == 0 ? "light"
                            : (roastSelection == 1 ? "medium" : "dark");
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
  }
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
#endif
}

void stopAcquisition() {
#if SMART_COFFEE_STANDALONE_SVM30
  svm30Capture.reset();
  aiRf30Roast = AiRf30Return::Roast::NONE;
#endif
  aiRf30Pending = false;
  aiRf30SessionToken = 0;
  acqState = AcqState::IDLE;
  acqCycle = 0;
  acqSampleIdx = 0;
  acqStateBeforePause = AcqState::IDLE;
  acqPausedElapsedMs = 0;
  acqPauseStartMs = 0;
  acqMode = AcquisitionMode::NONE;
  setActuators();
#if !SMART_COFFEE_STANDALONE_SVM30
  Serial.println(F("{\"event\":\"ACQ_STOP\",\"phase\":\"idle\"}"));
#endif
}

void pauseAcquisition() {
  if (acqState != AcqState::COLLECTING && acqState != AcqState::PURGING) {
    return;
  }
  acqStateBeforePause = acqState;
  acqPausedElapsedMs = millis() - acqPhaseStartMs;
  acqPauseStartMs = millis();
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
  acqPausedTotalMs += static_cast<uint32_t>(millis() - acqPauseStartMs);
  acqPauseStartMs = 0;
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

  const uint32_t nowMs = millis();
  const uint32_t durationMs = (acqState == AcqState::PURGING
                                   ? ACQ_PURGE_SECONDS
                                   : ACQ_COLLECTION_SECONDS) * 1000UL;
  if (!AcquisitionTiming::due(nowMs, acqPhaseStartMs, durationMs)) {
    return;
  }
  const uint32_t lateMs =
      AcquisitionTiming::lateness(nowMs, acqPhaseStartMs, durationMs);
  if (lateMs >= ACQ_MAX_PHASE_LATENESS_MS) {
    Serial.print(F("{\"event\":\"ACQ_TIMING_FAULT\",\"late_ms\":"));
    Serial.print(lateMs);
    Serial.println(F(",\"reason\":\"phase_deadline_missed\"}"));
    stopAcquisition(); // listener quarantines partial CSV on ACQ_STOP
    sendNextionAlert("Timing error", "Sampling deadline missed",
                     "Cancel and retry");
    return;
  }
  // Preserve the exact scheduled boundary rather than accumulating the
  // latency of callbacks (including ADC read, Nextion TX and task cadence).
  const uint32_t nextPhaseStartMs =
      AcquisitionTiming::boundary(acqPhaseStartMs, durationMs);

  if (acqState == AcqState::PURGING) {
    // Transisi Purging -> Collecting pada siklus yang sama (acqCycle).
    acqState = AcqState::COLLECTING;
    acqPhaseStartMs = nextPhaseStartMs;
    acqSampleIdx = 0;
    setActuators();

#if !SMART_COFFEE_STANDALONE_SVM30
    Serial.print(F("{\"event\":\"PHASE_CHANGE\",\"cycle\":"));
    Serial.print(acqCycle);
    Serial.print(F(",\"phase\":\"collecting\"}"));
    Serial.println();
#endif
  } else if (acqState == AcqState::COLLECTING) {
    if (acqCycle < ACQ_REPETITIONS) {
      // Lanjut ke siklus berikutnya: increment cycle -> PURGING.
      acqCycle++;
      acqState = AcqState::PURGING;
      acqPhaseStartMs = nextPhaseStartMs;
      acqSampleIdx = 0;
      setActuators();

#if !SMART_COFFEE_STANDALONE_SVM30
      Serial.print(F("{\"event\":\"PHASE_CHANGE\",\"cycle\":"));
      Serial.print(acqCycle);
      Serial.print(F(",\"phase\":\"purging\"}"));
      Serial.println();
#endif
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
          // In the standalone build, doInference() uses the 30-feature MCU
          // accumulator and SHA-pinned SVM in Flash, with no Pi/USB data.
          doInference();
          showNextionPage("pResult");
          updateNextionInferenceResult();
#if !SMART_COFFEE_STANDALONE_SVM30
          char history[UI_HISTORY_TEXT_CAPACITY] = {};
          snprintf(history, sizeof(history), "T-%04u  %s  AI N/A", testSequence,
                   inference.predictLabel());
          addUiHistory(history);
          ++testSequence;
#if ENABLE_PI_RF30_RETURN
          if (acqTotalSamples == 900 && aiRf30SessionToken != 0) {
            aiRf30Pending = true;
            aiRf30Deadline = millis() + AI_RF30_REPLY_TIMEOUT_MS;
            char token[9] = {};
            AiRf30Return::tokenHex(aiRf30SessionToken, token,sizeof(token));
            Serial.print(F("{\"event\":\"AI_AWAITING_RESULT\",\"token\":\""));
            Serial.print(token);
            Serial.println(F("\",\"samples\":900,\"window_ms\":30000}"));
          } else {
            Serial.println(F("{\"event\":\"AI_RESULT_UNAVAILABLE\",\"reason\":\"invalid_sample_count\"}"));
          }
#else
          Serial.println(F("{\"event\":\"AI_RESULT_UNAVAILABLE\",\"reason\":\"release_gate_disabled\"}"));
#endif
#else
          ++testSequence;
#endif
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
#if !SMART_COFFEE_STANDALONE_SVM30
  Serial.print(F("{\"event\":\"ACQ_COMPLETE\",\"cycles\":"));
  Serial.print(ACQ_REPETITIONS);
  Serial.print(F(",\"total_samples\":"));
  Serial.print(acqTotalSamples);
  Serial.print(F(",\"feat_count\":"));
  Serial.print(inference.getFeatureCount());
  Serial.print(F(",\"elapsed_active_ms\":"));
  Serial.print(static_cast<uint32_t>(millis() - acqStartMs - acqPausedTotalMs));
  Serial.print(F(",\"paused_ms\":"));
  Serial.print(acqPausedTotalMs);
  Serial.print(F(",\"target_active_ms\":"));
  Serial.print(static_cast<uint32_t>(ACQ_PURGE_SECONDS + ACQ_COLLECTION_SECONDS) *
               ACQ_REPETITIONS * 1000UL);
  Serial.println(F("}"));
#endif
}

void doInference() {
#if SMART_COFFEE_STANDALONE_SVM30
  aiRf30Roast = AiRf30Return::Roast::NONE;
  if (acqMode != AcquisitionMode::AI_TEST ||
      acqTotalSamples != EmbeddedSvm30::kSamples ||
      !svm30Capture.complete()) return;
  if (standaloneFreeRam() < 2048) return;
  float raw[EmbeddedSvm30::kNumFeatures] = {};
  if (!svm30Capture.copyFeatures(raw)) return;
  const EmbeddedSvm30::RoastClass predicted =
      EmbeddedSvm30::Classifier::predict(raw);
  switch (predicted) {
    case EmbeddedSvm30::DARK: aiRf30Roast=AiRf30Return::Roast::DARK; break;
    case EmbeddedSvm30::LIGHT: aiRf30Roast=AiRf30Return::Roast::LIGHT; break;
    case EmbeddedSvm30::MEDIUM: aiRf30Roast=AiRf30Return::Roast::MEDIUM; break;
    default: break; // fail-closed; Nextion will show N/A
  }
#else
  inference.printResult();
#endif
}

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
    nextionRunUiSlot = 0;
    updateNextionRunStatus();
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
  // pTake displays the data-acquisition contract even while IDLE.
  // acqMode is NONE before START; show duration from common 30-cycle contract.
  snprintf(cycles, sizeof(cycles), "%u", ACQ_DATA_REPETITIONS);
  buildTakeFilename(filename, sizeof(filename), true);
  nextion.text("tRoast", ROAST_OPTIONS[roastSelection]);
  nextion.text("tOrigin", ORIGIN_OPTIONS[originSelection]);
  nextion.text("tBatch", batch);
  nextion.text("tCycles", cycles);
  nextion.text("tFile", filename);

  // pTake is the pre-start form. Active sampling runs on pDataRun (page 3).
#if !SMART_COFFEE_STANDALONE_SVM30
  const bool ready = ROAST_OPTIONS[roastSelection][0] != '\0' &&
                     ORIGIN_OPTIONS[originSelection][0] != '\0' &&
                     batchNumber > 0 && ACQ_DATA_REPETITIONS > 0 &&
                     filename[0] != '\0';
#endif

#if SMART_COFFEE_STANDALONE_SVM30
  // Take Data has no external receiver/storage in standalone mode.
  nextion.text("tStat", "MODE DATA TIDAK TERSEDIA");
  nextion.textColor("tStat", NEXTION_STATUS_RED);
  nextion.touch("mStart", false);
#else
  nextion.text("tStat", ready ? "Siap untuk pengambilan data"
                              : "Data belum lengkap");
  nextion.textColor("tStat",
                    ready ? NEXTION_STATUS_GREEN : NEXTION_STATUS_RED);
  nextion.touch("mStart", ready);
#endif
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
#if SMART_COFFEE_STANDALONE_SVM30
  nextion.text("tMode", "SVM30 BENCH");
#else
  nextion.text("tMode", "AI NOT VALIDATED");
#endif
  nextion.text("tAtmega", arrayReady ? "READY" : "ERROR");
  // Pi availability and AI inference have not been proven end-to-end.
#if SMART_COFFEE_STANDALONE_SVM30
  nextion.text("tPi", "LOCAL MCU");
#else
  nextion.text("tPi", "AI N/A");
#endif
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
#if SMART_COFFEE_STANDALONE_SVM30
  nextion.text("tFw", "SVM30-LOCAL");
#else
  nextion.text("tFw", "DATA30-AI30");
#endif
}

void updateNextionTestRunPage() {
  char testId[24] = {};
  snprintf(testId, sizeof(testId), "TEST T-%04u", testSequence);
  nextion.text("tTestId", testId);
#if SMART_COFFEE_STANDALONE_SVM30
  nextion.text("tPi", "LOCAL MCU");
#else
  nextion.text("tPi", "AI N/A");
#endif
  nextion.progress("jAI", 0);
  nextion.text("tStep1", "RUNNING");
  nextion.text("tStep2", "WAIT");
  nextion.text("tStep3", "WAIT");
  nextion.text("tStep4", "N/A");
  nextion.text("tEta", "EST. REMAINING 15:00");
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
  nextion.text("tStep4", "N/A");

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
  nextion.text("tBase", baselineCaptureActive ? "RECORDING" : "READY 60S");
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
  if (strcmp(nextionPageName, "pDataRun") != 0 ||
      acqMode != AcquisitionMode::LABELED_DATA) {
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

  // One field per 125ms slot, and only if it fits the free 9600-baud TX
  // queue. Failure to enqueue only drops an LCD refresh, NEVER an ADC sample.
  const uint8_t slot = nextionRunUiSlot;
  nextionRunUiSlot = (nextionRunUiSlot + 1) % 8;
  switch (slot) {
  case 0:
    buildTakeFilename(text, sizeof(text), false);
    nextion.tryText("tSample", text);
    break;
  case 1:
    snprintf(text, sizeof(text), "CYCLE %lu / %u", (unsigned long)cycle,
             ACQ_REPETITIONS);
    nextion.tryText("tCycle", text);
    break;
  case 2:
    nextion.tryProgress("jCycle", cyclePercent > 100 ? 100 : cyclePercent);
    break;
  case 3:
    nextion.tryText("tPhase", acqState == AcqState::PAUSED ? "paused"
                                                               : acqStateName());
    break;
  case 4:
    snprintf(text, sizeof(text), "%02lu:%02lu", (unsigned long)(remaining / 60),
             (unsigned long)(remaining % 60));
    nextion.tryText("tRemain", text);
    break;
  case 5:
    if (sensors.environmentValid()) {
      char value[16] = {};
      dtostrf(sensors.getTemperatureC(), 0, 1, value);
      snprintf(text, sizeof(text), "%s C", value);
      nextion.tryText("tTemp", text);
    } else {
      nextion.tryText("tTemp", "N/A");
    }
    break;
  case 6:
    if (sensors.environmentValid()) {
      char value[16] = {};
      dtostrf(sensors.getHumidityRh(), 0, 1, value);
      snprintf(text, sizeof(text), "%s %%RH", value);
      nextion.tryText("tHum", text);
    } else {
      nextion.tryText("tHum", "N/A");
    }
    break;
  default:
    updateNextionSensorSnapshot();
    break;
  }
}

void updateNextionSensorSnapshot() {
  if (strcmp(nextionPageName, "pDataRun") != 0) {
    return;
  }
  if (!sensorsReady) {
    nextion.text("tSensors", "ADC ERROR");
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
  if (nextion.tryText("tSensors", text)) {
    nextionSensorIndex = (index + 1) % NUM_SENSORS;
  }
}

void updateNextionInferenceResult() {
#if SMART_COFFEE_STANDALONE_SVM30
  const char *label = AiRf30Return::label(aiRf30Roast);
#else
  const char *label = aiRf30Roast != AiRf30Return::Roast::NONE
                          ? AiRf30Return::label(aiRf30Roast)
                          : inference.predictLabel();
#endif
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

void restoreNextionPageAfterBoot() {
  // The HMI can reboot independently from the ATmega (for example after
  // flashing a TFT via microSD). Restore the page that matches the current
  // acquisition state instead of leaving the display on pSplash.
  if (acqState == AcqState::COLLECTING ||
      acqState == AcqState::PURGING ||
      acqState == AcqState::PAUSED) {
    if (acqMode == AcquisitionMode::AI_TEST) {
      showNextionPage("pTestRun");
      updateNextionTestRunPage();
    } else {
      showNextionPage("pDataRun");
      updateNextionRunStatus();
    }
  } else {
    showNextionPage("pHome");
  }
  nextionHomeSent = true;
}

void handleNextionEvent(const char *event) {
  if (event == nullptr || strncmp(event, "EVT:", 4) != 0) {
    return;
  }

  Serial.print(F("{\"nextion_event\":\""));
  Serial.print(event);
  Serial.println(F("\"}"));

  if (strcmp(event, "EVT:HMI_READY") == 0) {
    restoreNextionPageAfterBoot();
  } else if (strcmp(event, "EVT:HOME") == 0) {
    if (baselineCaptureActive) {
      stopBaselineCapture("cancelled_by_operator");
    }
    if (acqState != AcqState::IDLE) {
      stopAcquisition();
    }
    showNextionPage("pHome");
  } else if (baselineCaptureActive && strcmp(event, "EVT:CAL_START") != 0) {
    Serial.println(F("{\"event\":\"UI_NAV_BUSY_REJECTED\",\"reason\":\"baseline_active\"}"));
    return;
  } else if (strcmp(event, "EVT:TAKE_OPEN") == 0) {
    if (acqState == AcqState::IDLE) {
      showNextionPage("pTake");
    } else {
      Serial.println(F("{\"event\":\"UI_NAV_BUSY_REJECTED\"}"));
    }
  } else if (strcmp(event, "EVT:TEST_START") == 0) {
    if (acqState == AcqState::IDLE) {
      showNextionPage("pTest");
    } else {
      Serial.println(F("{\"event\":\"UI_NAV_BUSY_REJECTED\"}"));
    }
  } else if (strcmp(event, "EVT:HISTORY") == 0) {
    if (acqState == AcqState::IDLE) {
      showNextionPage("pHistory");
    } else {
      Serial.println(F("{\"event\":\"UI_NAV_BUSY_REJECTED\"}"));
    }
  } else if (strcmp(event, "EVT:SETTINGS") == 0) {
    if (acqState == AcqState::IDLE) {
      showNextionPage("pSettings");
    } else {
      Serial.println(F("{\"event\":\"UI_NAV_BUSY_REJECTED\"}"));
    }
  } else if ((strcmp(event, "EVT:ROAST_NEXT") == 0 ||
              strcmp(event, "EVT:ROAST_PREV") == 0 ||
              strcmp(event, "EVT:ORIGIN_NEXT") == 0 ||
              strcmp(event, "EVT:ORIGIN_PREV") == 0 ||
              strcmp(event, "EVT:BATCH_INC") == 0 ||
              strcmp(event, "EVT:BATCH_DEC") == 0) &&
             acqState != AcqState::IDLE) {
    Serial.println(F("{\"event\":\"UI_SELECTION_LOCKED_DURING_ACQ\"}"));
    return;
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
#if SMART_COFFEE_STANDALONE_SVM30
    sendNextionAlert("Mode data nonaktif", "Standalone: tanpa simpan CSV",
                     "Gunakan START AI TEST");
#else
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
      // Ignore duplicate START without leaving active DataRun.
      updateNextionRunStatus();
    }
#endif
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
#if SMART_COFFEE_STANDALONE_SVM30
    sendNextionAlert("Record nonaktif", "Tidak ada penyimpanan data",
                     "Gunakan START AI TEST");
#else
    if (strcmp(nextionPageName, "pCal") != 0) {
      if (acqState == AcqState::IDLE) {
        showNextionPage("pCal");
      } else {
        Serial.println(F("{\"event\":\"UI_NAV_BUSY_REJECTED\"}"));
      }
    } else if (!sensorsReady || !sensors.allAdcAvailable()) {
      sendNextionAlert("Calibration error", "ADC belum siap",
                       "Periksa I2C lalu retry");
    } else if (acqState != AcqState::IDLE || baselineCaptureActive) {
      sendNextionAlert("Calibration busy", "Akuisisi sedang berjalan",
                       "Cancel run lebih dulu");
    } else {
      // Baseline ADC capture ONLY. Never rewrite R0/EEPROM on HMI press.
      actuator.setPurging();
      baselineCaptureActive = true;
      baselineSampleIdx = 0;
      nextion.text("tBase", "REC 0/60");
      Serial.print(F("{\"event\":\"BASELINE_START\",\"protocol\":\"clean_air_adc.v1\",\"fw_build_id\":\""));
      Serial.print(F(SMART_COFFEE_BUILD_ID));
      Serial.println(F("\",\"target_samples\":60,\"interval_ms\":1000,\"eeprom_r0_modified\":false}"));
    }
#endif
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
#if SMART_COFFEE_STANDALONE_SVM30
    sendNextionAlert("Simpan nonaktif", "Hasil hanya tampil di LCD",
                     "Tidak ada penyimpanan CSV");
#else
    Serial.print(F("{\"event\":\"RESULT_EXPORT\",\"roast\":\""));
    Serial.print(aiRf30Roast != AiRf30Return::Roast::NONE
                     ? AiRf30Return::label(aiRf30Roast)
                     : inference.predictLabel());
    Serial.println(F("\",\"origin\":null,\"confidence\":null}"));
    sendNextionAlert("Result exported", "Hasil dikirim ke Serial USB",
                     "History RAM tetap tersimpan");
#endif
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

#if !SMART_COFFEE_STANDALONE_SVM30
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
#endif
}

void uiCallback() {
  if (acqMode == AcquisitionMode::LABELED_DATA &&
      (acqState == AcqState::PURGING || acqState == AcqState::COLLECTING ||
       acqState == AcqState::PAUSED)) {
    updateNextionRunStatus();
  }
}

void expireAiRf30Reply() {
  if (!aiRf30Pending ||
      static_cast<int32_t>(millis() - aiRf30Deadline) < 0) {
    return;
  }
  aiRf30Pending = false; // a late or repeated packet can never alter pResult
  Serial.println(F("{\"event\":\"AI_RESULT_TIMEOUT\",\"result\":\"N/A\"}"));
}

void processAiRf30Reply(const char *cmd) {
#if ENABLE_PI_RF30_RETURN
  uint32_t token = 0;
  AiRf30Return::Roast roast = AiRf30Return::Roast::NONE;
  if (!AiRf30Return::decode(cmd, &token, &roast)) {
    Serial.println(F("{\"event\":\"AI_RESULT_NACK\",\"reason\":\"bad_packet\"}"));
    return;
  }
  expireAiRf30Reply();
  if (!aiRf30Pending || token != aiRf30SessionToken ||
      acqState != AcqState::IDLE ||
      strcmp(nextionPageName, "pResult") != 0) {
    Serial.println(F("{\"event\":\"AI_RESULT_NACK\",\"reason\":\"wrong_session_or_state\"}"));
    return;
  }
  aiRf30Pending = false; // consume nonce before HMI updates / serial output
  aiRf30Roast = roast;
  updateNextionInferenceResult();
  char tokenText[9] = {};
  AiRf30Return::tokenHex(token,tokenText,sizeof(tokenText));
  Serial.print(F("{\"event\":\"AI_RESULT_ACK\",\"token\":\""));
  Serial.print(tokenText);
  Serial.print(F("\",\"roast\":\""));
  Serial.print(AiRf30Return::label(roast));
  Serial.println(F("\",\"origin\":null,\"confidence\":null}"));
  char history[UI_HISTORY_TEXT_CAPACITY] = {};
  snprintf(history,sizeof(history),"T-%04u RF30 %s",testSequence - 1,
           AiRf30Return::label(roast));
  addUiHistory(history);
#else
  (void)cmd;
  Serial.println(F("{\"event\":\"AI_RESULT_NACK\",\"reason\":\"release_gate_disabled\"}"));
#endif
}

void processCommand(const char *cmd) {
  if (strncmp(cmd, "#rf30:", 6) == 0) {
    processAiRf30Reply(cmd);
  } else if (strcmp(cmd, "#start") == 0 || strcmp(cmd, "#1") == 0) {
    if (acqState == AcqState::IDLE && !baselineCaptureActive) {
      if (sensorsReady && sensors.allAdcAvailable()) {
        startAcquisition();
      } else {
        Serial.println(F("{\"error\":\"ACQ_REJECTED\",\"reason\":\"ADC not ready\"}"));
      }
    } else {
      Serial.println(F("{\"warn\":\"Akuisisi sudah berjalan. Kirim #stop; "
                       "terlebih dahulu.\"}"));
    }
  } else if (strcmp(cmd, "#stop") == 0 || strcmp(cmd, "#0") == 0) {
    if (baselineCaptureActive) {
      stopBaselineCapture("operator_serial_stop");
    } else {
      stopAcquisition();
    }
  } else if (strcmp(cmd, "#help") == 0 || strcmp(cmd, "#2") == 0 ||
             strcmp(cmd, "#status") == 0) {
    printWelcome();
  } else if (strcmp(cmd, "#scan") == 0) {
    if (acqState == AcqState::IDLE && !baselineCaptureActive) {
      scanI2C();
    } else {
      Serial.println(F("{\"warn\":\"I2C scan disabled during acquisition\"}"));
    }

    // ── Valve debug commands ────────────────────────────────────────────────
  } else if (strcmp(cmd, "#valve_on") == 0) {
#if ENABLE_MANUAL_ACTUATOR_TESTS
    if (acqState != AcqState::IDLE) {
      Serial.println(
          F("{\"warn\":\"Tidak bisa tes valve saat akuisisi berjalan.\"}"));
      return;
    }
    // Aktifkan solenoid → Port 1/33 terbuka (posisi COLLECTING)
    actuator.setCollecting();
    Serial.println(
        F("{\"valve\":\"ON\",\"port\":\"1/33\",\"mode\":\"collecting\"}"));
#else
    Serial.println(F("{\"error\":\"MANUAL_ACTUATOR_DISABLED\"}"));
#endif

  } else if (strcmp(cmd, "#valve_off") == 0) {
#if ENABLE_MANUAL_ACTUATOR_TESTS
    if (acqState != AcqState::IDLE) {
      Serial.println(
          F("{\"warn\":\"Tidak bisa tes valve saat akuisisi berjalan.\"}"));
      return;
    }
    // Matikan solenoid → Port 3/11 terbuka (posisi PURGING / spring return)
    actuator.setPurging();
    Serial.println(
        F("{\"valve\":\"OFF\",\"port\":\"3/11\",\"mode\":\"purging\"}"));
#else
    Serial.println(F("{\"error\":\"MANUAL_ACTUATOR_DISABLED\"}"));
#endif

  } else if (strcmp(cmd, "#valve_test") == 0) {
#if ENABLE_MANUAL_ACTUATOR_TESTS
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
#else
    Serial.println(F("{\"error\":\"MANUAL_ACTUATOR_DISABLED\"}"));
#endif

  } else if (strcmp(cmd, "#pin_scan") == 0) {
    // Pemindaian pin legacy berbahaya: mengubah D19/RX1 dan SDA D20.
    // Dinonaktifkan permanen pada firmware yang berjalan.
    Serial.println(F("{\"error\":\"PIN_SCAN_DISABLED\"}"));


  } else {
    Serial.print(F("{\"warn\":\"Perintah tidak dikenal\",\"cmd\":\""));
    Serial.print(cmd);
    Serial.println(F("\"}"));
  }
}

void stopBaselineCapture(const char *reason) {
  if (!baselineCaptureActive) {
    return;
  }
  baselineCaptureActive = false;
  actuator.stop();
  Serial.print(F("{\"event\":\"BASELINE_ABORT\",\"samples\":"));
  Serial.print(baselineSampleIdx);
  Serial.print(F(",\"reason\":\""));
  Serial.print(reason);
  Serial.println(F("\"}"));
  if (strcmp(nextionPageName, "pCal") == 0) {
    nextion.text("tBase", "CANCELLED");
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ADS CALLBACK — Baca semua sensor, proses state machine, kirim JSON
// ═══════════════════════════════════════════════════════════════════════════════

void adsCallback() {
  // Pembacaan harus dikirim dengan identitas fase SAAT dibaca. Jangan
  // transisikan fase sebelum menulis frame, khususnya pada ACQ_COMPLETE:
  // jika event COMPLETE muncul lebih dulu, listener menutup CSV terlalu dini.
  sensors.readAll();
  if (baselineCaptureActive) {
    ++baselineSampleIdx;
    sensors.printJsonData("baseline", 0, baselineSampleIdx);
    if (baselineSampleIdx >= BASELINE_SAMPLES) {
      Serial.print(F("{\"event\":\"BASELINE_COMPLETE\",\"samples\":"));
      Serial.print(baselineSampleIdx);
      Serial.println(F("}"));
      baselineCaptureActive = false;
      actuator.stop();
      nextion.text("tBase", "CAPTURE DONE");
    } else if (baselineSampleIdx % 5 == 0) {
      char label[20] = {};
      snprintf(label, sizeof(label), "REC %u/%u", baselineSampleIdx,
               BASELINE_SAMPLES);
      nextion.text("tBase", label);
    }
    return;
  }

  // Kirim hanya frame akuisisi aktif, bukan idle/paused/status tanpa siklus.
  if (acqState == AcqState::COLLECTING || acqState == AcqState::PURGING) {
    ++acqSampleIdx;
    acqTotalSamples++;
#if SMART_COFFEE_STANDALONE_SVM30
    // No USB listener/CSV; strictly process exactly one real ADC reading.
    if (acqMode == AcquisitionMode::AI_TEST) {
      const bool available =
          sensors.adcAvailable(SENSOR_TGS822) &&
          sensors.adcAvailable(SENSOR_TGS2602) &&
          sensors.adcAvailable(SENSOR_TGS816) &&
          sensors.adcAvailable(SENSOR_MQ8);
      const EmbeddedSvm30::Phase phase =
          acqState == AcqState::PURGING ? EmbeddedSvm30::PURGING
                                       : EmbeddedSvm30::COLLECTING;
      if (!available ||
          !svm30Capture.add(sensors.getAdcArray(),
                           static_cast<uint8_t>(acqCycle), phase,
                           static_cast<uint8_t>(acqSampleIdx))) {
        stopAcquisition();  // valve solenoid OFF immediately
        sendNextionAlert("AI Test invalid", "Data sensor tidak lengkap",
                         "Cancel dan ulangi");
        return;
      }
    }
#else
    if (acqState == AcqState::COLLECTING) {
      inference.accumulate(sensors.getAdcArray());
    }
    sensors.printJsonData(acqStateName(), acqCycle, acqSampleIdx);
#endif
  }

  // State changes run on absolute deadlines in loop(), not AFTER an ADC
  // sample. LCD refresh runs separately on best-effort 125ms slots.
  if (acqMode == AcquisitionMode::AI_TEST) {
    updateNextionTestRunStatus();
  }
}
