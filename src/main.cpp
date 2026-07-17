// ═════════════════════════════════════════════════════════════════════════════
// Smart Coffee E-NOSE
// Portable Embedded AI untuk Standarisasi Roasting Kopi
// Klasifikasi: Light / Medium / Dark Roast
//
// Alur akuisisi per sampel:
//   COLLECTING (pompa+valve ON, ujung selang ke sampel, default 180 s)
//     → PURGING (pompa ON, valve OFF/ke udara, default 60 s)
//     → ulangi ACQ_REPETITIONS kali
//   Setelah semua siklus selesai → inferensi on-device (TinyML)
// ═════════════════════════════════════════════════════════════════════════════
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Preferences.h>
#include "TaskScheduler.h"
#include "ArduinoJson.h"
#include "ADS1X15.h"
// #include "Adafruit_SHT31.h"   // SHT31 dinonaktifkan sementara
#include "MQUnifiedsensor.h"
#include "TGS2620.h"

// ─── On-Device Inference ─────────────────────────────────────────────────────
// Ubah ke 1 SETELAH model_rf.h di-generate oleh script 4_train_rf.py
// kemudian jalankan: pio run --target upload
#define USE_ON_DEVICE_INFERENCE 0
#if USE_ON_DEVICE_INFERENCE
#include "model_rf.h"   // dihasilkan oleh micromlgen (scripts/4_train_rf.py)
#endif

// ─── Debug ────────────────────────────────────────────────────────────────────
#define DEBUG 0

// ─── NVS Namespace ────────────────────────────────────────────────────────────
#define PREF_NAMESPACE_ENOSE_R0 "enose_r0"

// ─── ADC 16→8 bit scaler (waveform Nextion) ──────────────────────────────────
#define ADC16TO8 0.0038909912109375

// ─── I2C Addresses ────────────────────────────────────────────────────────────
#define I2C_ADDR_ADS1   0x48   // ADDR→GND
#define I2C_ADDR_ADS2   0x49   // ADDR→VCC
// #define I2C_ADDR_SHT21  0x44   // SHT31 dinonaktifkan sementara

// ─── GPIO / PWM ───────────────────────────────────────────────────────────────
#define IO_INTERNAL_LED  2
#define IO_PWM1         27   // valve  — arahkan aliran udara ke sampel / ke udara bebas
#define IO_PWM2         23   // pompa  — menghisap udara melalui ruang sensor
#define LEDC_CHAN_PWM1   0
#define LEDC_CHAN_PWM2   1
#define LEDC_FREQ       5000
#define LEDC_RESO          8  // 8-bit: 0–255

// ─── ADS1115 Channel Map ──────────────────────────────────────────────────────
#define ADS_GAIN          0   // ±6.144 V
#define ADS_VOLTAGE    6.144
#define ADS_ADC           16
#define ADS1_CHAN_MQ137   0
#define ADS1_CHAN_MQ3     1
#define ADS1_CHAN_MQ138   2
#define ADS1_CHAN_MQ135   3
#define ADS2_CHAN_MQ2     0
#define ADS2_CHAN_MQ136   1
#define ADS2_CHAN_TGS822  2
#define ADS2_CHAN_TGS2620 3

// ─── Nextion Waveform ─────────────────────────────────────────────────────────
#define NEX_WAVE1_CID 2
#define NEX_WAVE2_CID 3
#define NEX_WAVE1_CHAN_MQ135    0
#define NEX_WAVE1_CHAN_MQ136    1
#define NEX_WAVE1_CHAN_MQ137    2
#define NEX_WAVE1_CHAN_MQ138    3
#define NEX_WAVE2_CHAN_MQ2      0
#define NEX_WAVE2_CHAN_MQ3      1
#define NEX_WAVE2_CHAN_TGS822   2
#define NEX_WAVE2_CHAN_TGS2620  3

// ─── Task Scheduler Intervals ─────────────────────────────────────────────────
#define TASK_INTERVAL_MS_ADS    1000   // 1 sampel/detik → 180 sampel/siklus
#define TASK_INTERVAL_MS_SERIAL  100   // polling Serial 10×/detik

// ─── Konfigurasi Akuisisi ─────────────────────────────────────────────────────
#define ACQ_COLLECTION_SECONDS  180   // durasi menghirup aroma kopi (detik)
#define ACQ_PURGE_SECONDS        60   // durasi purging ke udara bebas (detik)
#define ACQ_REPETITIONS          10   // jumlah pengulangan siklus
// Total sampel collecting: ACQ_COLLECTION_SECONDS × ACQ_REPETITIONS = 1800

// ─── Feature Flags ────────────────────────────────────────────────────────────
#define USE_NEXTION_GRAPH         0
#define IS_CALIBRATING_GAS_SENSOR 1   // 1 = kalibrasi ulang, 0 = pakai nilai tersimpan
#define USE_PPM                   1   // 1 = sertakan nilai PPM di JSON

// ─── Serial Aliases ───────────────────────────────────────────────────────────
#define pcSerial  Serial
#define nexSerial Serial2

#define USE_ADS   0
#define USE_SHT31 0
// =============================================================================
//  SmartCoffeeSystem
// =============================================================================
class SmartCoffeeSystem {
public:
    SmartCoffeeSystem();
    void begin();
    void run();

private:
    // ── State akuisisi ───────────────────────────────────────────────────────
    enum class AcqState { IDLE, COLLECTING, PURGING, COMPLETE };

    // ── Static trampolines (TaskScheduler memerlukan fungsi static/global) ───
    static SmartCoffeeSystem* instance_;
    static void adsCallbackStatic();
    static void serialReadCallbackStatic();
    static void core0TaskStatic(void* param);

    // ── Private methods ──────────────────────────────────────────────────────
    void fail();
    void initHardwares();
    void initCheckSensors();
    void initTasks();

    void adsCallback();
    void serialReadCallback();
    void processCommand(const String& cmd);
    void core0Task(void* param);
    void graphCallback();
    void sendWave(int cid, int chan, int val);

    // State machine akuisisi
    void startAcquisition();
    void stopAcquisition();
    void processAcquisitionState();
    void setAcquisitionActuators();
    const char* acqStateName() const;
    void printAcquisitionSummary();
    void doInference();

    // ── Hardware Objects ─────────────────────────────────────────────────────
    Preferences     pref_;
    TaskHandle_t    t0H_{};
    Scheduler       sch_;
    Task            task_ads_;
    Task            task_serial_;

    ADS1115         ads1_;
    ADS1115         ads2_;
    // Adafruit_SHT31  sht31_;   // SHT31 dinonaktifkan sementara

    MQUnifiedsensor mq135_;
    MQUnifiedsensor mq136_;
    MQUnifiedsensor mq137_;
    MQUnifiedsensor mq138_;
    MQUnifiedsensor mq2_;
    MQUnifiedsensor mq3_;
    TGS2620         tgs2620_;
    TGS2620         tgs822_;

    // ── Nilai ADC Mentah ─────────────────────────────────────────────────────
    uint16_t adc_mq135_   = 0;
    uint16_t adc_mq136_   = 0;
    uint16_t adc_mq137_   = 0;
    uint16_t adc_mq138_   = 0;
    uint16_t adc_mq2_     = 0;
    uint16_t adc_mq3_     = 0;
    uint16_t adc_tgs822_  = 0;
    uint16_t adc_tgs2620_ = 0;

    // ── State Akuisisi ───────────────────────────────────────────────────────
    AcqState      acq_state_          = AcqState::IDLE;
    unsigned long acq_phase_start_ms_ = 0;
    uint32_t      acq_cycle_          = 0;   // siklus aktif (1-based)
    uint32_t      acq_sample_idx_     = 0;   // indeks sampel dalam fase ini (0-based)
    uint32_t      acq_total_samples_  = 0;   // total sampel keseluruhan (collecting+purging)

    // Running sum & max ADC untuk fitur inferensi on-device (fase collecting)
    // Urutan indeks: [mq135, mq136, mq137, mq138, mq2, mq3, tgs822, tgs2620]
    double   feat_sum_[8]  = {};
    uint16_t feat_max_[8]  = {};
    uint32_t feat_count_   = 0;

    // ── Buffer Command Serial ─────────────────────────────────────────────────
    char m6r_buf_[256]{};
    int  m6r_buf_i_ = 0;
};

SmartCoffeeSystem* SmartCoffeeSystem::instance_ = nullptr;

// ─────────────────────────────────────────────────────────────────────────────
//  Constructor
// ─────────────────────────────────────────────────────────────────────────────
SmartCoffeeSystem::SmartCoffeeSystem()
    : task_ads_   (TASK_INTERVAL_MS_ADS,    TASK_FOREVER, &SmartCoffeeSystem::adsCallbackStatic),
      task_serial_(TASK_INTERVAL_MS_SERIAL, TASK_FOREVER, &SmartCoffeeSystem::serialReadCallbackStatic),
      ads1_(I2C_ADDR_ADS1),
      ads2_(I2C_ADDR_ADS2),
      // sht31_(),   // SHT31 dinonaktifkan sementara
      mq135_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-135"),
      mq136_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-136"),
      mq137_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-137"),
      mq138_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-138"),
      mq2_  ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-2"),
      mq3_  ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-3"),
      tgs2620_(),
      tgs822_()
{
    instance_ = this;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Public entry points
// ─────────────────────────────────────────────────────────────────────────────
void SmartCoffeeSystem::begin() {
    initHardwares();
    initCheckSensors();
    initTasks();
}

void SmartCoffeeSystem::run() {
    sch_.execute();
}

// ─────────────────────────────────────────────────────────────────────────────
//  Static trampolines
// ─────────────────────────────────────────────────────────────────────────────
void SmartCoffeeSystem::adsCallbackStatic()        { if (instance_) instance_->adsCallback();        }
void SmartCoffeeSystem::serialReadCallbackStatic() { if (instance_) instance_->serialReadCallback(); }
void SmartCoffeeSystem::core0TaskStatic(void* p)   { if (instance_) instance_->core0Task(p);         }

// ─────────────────────────────────────────────────────────────────────────────
//  fail()
// ─────────────────────────────────────────────────────────────────────────────
void SmartCoffeeSystem::fail() {
    while (1) {
        pcSerial.println("{\"error\":\"FATAL – system halted\"}");
        delay(1000);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  initHardwares()
// ─────────────────────────────────────────────────────────────────────────────
void SmartCoffeeSystem::initHardwares() {
    ledcSetup(LEDC_CHAN_PWM1, LEDC_FREQ, LEDC_RESO);
    ledcSetup(LEDC_CHAN_PWM2, LEDC_FREQ, LEDC_RESO);
    ledcAttachPin(IO_PWM1, LEDC_CHAN_PWM1);
    ledcAttachPin(IO_PWM2, LEDC_CHAN_PWM2);

    // Pastikan semua aktuator OFF saat boot
    ledcWrite(LEDC_CHAN_PWM1, 0);
    ledcWrite(LEDC_CHAN_PWM2, 0);

    Wire.begin();
    pcSerial.begin(115200);
    nexSerial.begin(9600);
}

// ─────────────────────────────────────────────────────────────────────────────
//  initCheckSensors()
// ─────────────────────────────────────────────────────────────────────────────
void SmartCoffeeSystem::initCheckSensors() {
    // SHT31 dinonaktifkan sementara
    // if (!sht31_.begin(I2C_ADDR_SHT21)) {
    //     pcSerial.println("{\"error\":\"SHT31 tidak ditemukan\"}");
    //     fail();
    // }
    // pcSerial.println(sht31_.isHeaterEnabled()
    //     ? "{\"info\":\"SHT31 heater ON\"}"
    //     : "{\"info\":\"SHT31 heater OFF\"}");

    if (!ads1_.isConnected()) { 
        pcSerial.println("{\"error\":\"ADS1115 #1 tidak ditemukan\"}"); 
        fail(); 
    }
    if (!ads2_.isConnected()) { 
        pcSerial.println("{\"error\":\"ADS1115 #2 tidak ditemukan\"}"); 
        fail(); 
    }

    ads1_.setGain(ADS_GAIN);
    ads2_.setGain(ADS_GAIN);

    // ── Konfigurasi RL & rasio udara bersih setiap sensor ────────────────────
    float mq135_rL = 20, ratio_mq135_air = 3.6;
    mq135_.setRegressionMethod(1); mq135_.setRL(mq135_rL);

    float mq136_rL = 20, ratio_mq136_air = 3.6;
    mq136_.setRegressionMethod(1); mq136_.setRL(mq136_rL);

    float mq137_rL = 20, ratio_mq137_air = 3.6;
    mq137_.setRegressionMethod(1); mq137_.setRL(mq137_rL);

    float mq138_rL = 20, ratio_mq138_air = 9.8;
    mq138_.setRegressionMethod(1); mq138_.setRL(mq138_rL);

    float mq2_rL   = 20, ratio_mq2_air   = 9.83;
    mq2_.setRegressionMethod(1);   mq2_.setRL(mq2_rL);

    float mq3_rL   = 20, ratio_mq3_air   = 60;
    mq3_.setRegressionMethod(1);   mq3_.setRL(mq3_rL);

    float tgs2620_rL = 20, ratio_tgs2620_air = 21;
    tgs2620_.setRL(tgs2620_rL); tgs2620_.setRatioAir(ratio_tgs2620_air);

    float tgs822_rL  = 20, ratio_tgs822_air  = 17;
    tgs822_.setRL(tgs822_rL);   tgs822_.setRatioAir(ratio_tgs822_air);

    pref_.begin(PREF_NAMESPACE_ENOSE_R0, false);

#if IS_CALIBRATING_GAS_SENSOR
    // ── Kalibrasi di udara bersih ─────────────────────────────────────────────
    pcSerial.println("{\"info\":\"Kalibrasi sensor gas di udara bersih...\"}");
    float calc_r0 = 0;

    for (int i = 0; i < 10; i++) { adc_mq135_ = ads1_.readADC(ADS1_CHAN_MQ135); mq135_.setADC(adc_mq135_); calc_r0 += mq135_.calibrate(ratio_mq135_air); }
    mq135_.setR0(calc_r0 / mq135_rL); pref_.putFloat("mq135", calc_r0); calc_r0 = 0;

    for (int i = 0; i < 10; i++) { adc_mq136_ = ads2_.readADC(ADS2_CHAN_MQ136); mq136_.setADC(adc_mq136_); calc_r0 += mq136_.calibrate(ratio_mq136_air); }
    mq136_.setR0(calc_r0 / mq136_rL); pref_.putFloat("mq136", calc_r0); calc_r0 = 0;

    for (int i = 0; i < 10; i++) { adc_mq137_ = ads1_.readADC(ADS1_CHAN_MQ137); mq137_.setADC(adc_mq137_); calc_r0 += mq137_.calibrate(ratio_mq137_air); }
    mq137_.setR0(calc_r0 / mq137_rL); pref_.putFloat("mq137", calc_r0); calc_r0 = 0;

    for (int i = 0; i < 10; i++) { adc_mq138_ = ads1_.readADC(ADS1_CHAN_MQ138); mq138_.setADC(adc_mq138_); calc_r0 += mq138_.calibrate(ratio_mq138_air); }
    mq138_.setR0(calc_r0 / mq138_rL); pref_.putFloat("mq138", calc_r0); calc_r0 = 0;

    for (int i = 0; i < 10; i++) { adc_mq2_ = ads2_.readADC(ADS2_CHAN_MQ2); mq2_.setADC(adc_mq2_); calc_r0 += mq2_.calibrate(ratio_mq2_air); }
    mq2_.setR0(calc_r0 / mq2_rL); pref_.putFloat("mq2", calc_r0); calc_r0 = 0;

    for (int i = 0; i < 10; i++) { adc_mq3_ = ads1_.readADC(ADS1_CHAN_MQ3); mq3_.setADC(adc_mq3_); calc_r0 += mq3_.calibrate(ratio_mq3_air); }
    mq3_.setR0(calc_r0 / mq3_rL); pref_.putFloat("mq3", calc_r0); calc_r0 = 0;

    for (int i = 0; i < 10; i++) { adc_tgs2620_ = ads2_.readADC(ADS2_CHAN_TGS2620); tgs2620_.setADC(adc_tgs2620_); calc_r0 += tgs2620_.calibrate(ratio_tgs2620_air); }
    tgs2620_.setR0(calc_r0 / tgs2620_rL); pref_.putFloat("tgs2620", calc_r0); calc_r0 = 0;

    for (int i = 0; i < 10; i++) { adc_tgs822_ = ads2_.readADC(ADS2_CHAN_TGS822); tgs822_.setADC(adc_tgs822_); calc_r0 += tgs822_.calibrate(ratio_tgs822_air); }
    tgs822_.setR0(calc_r0 / tgs822_rL); pref_.putFloat("tgs822", calc_r0);

    pcSerial.println("{\"info\":\"Kalibrasi selesai\"}");

#else
    // ── Muat nilai R0 dari NVS ────────────────────────────────────────────────
    float mq135_r0   = pref_.getFloat("mq135");
    float mq136_r0   = pref_.getFloat("mq136");
    float mq137_r0   = pref_.getFloat("mq137");
    float mq138_r0   = pref_.getFloat("mq138");
    float mq2_r0     = pref_.getFloat("mq2");
    float mq3_r0     = pref_.getFloat("mq3");
    float tgs2620_r0 = pref_.getFloat("tgs2620");
    float tgs822_r0  = pref_.getFloat("tgs822");

    if (mq135_r0 <= 0 || mq136_r0 <= 0 || mq137_r0 <= 0 || mq138_r0 <= 0 ||
        mq2_r0   <= 0 || mq3_r0   <= 0 || tgs2620_r0 <= 0 || tgs822_r0 <= 0) {
        pcSerial.println("{\"error\":\"Sensor belum dikalibrasi. Set IS_CALIBRATING_GAS_SENSOR=1, flash di udara bersih, lalu kembalikan ke 0.\"}");
        fail();
    }
    mq135_.setR0(mq135_r0   / mq135_rL);
    mq136_.setR0(mq136_r0   / mq136_rL);
    mq137_.setR0(mq137_r0   / mq137_rL);
    mq138_.setR0(mq138_r0   / mq138_rL);
    mq2_.setR0  (mq2_r0     / mq2_rL);
    mq3_.setR0  (mq3_r0     / mq3_rL);
    tgs2620_.setR0(tgs2620_r0 / tgs2620_rL);
    tgs822_.setR0 (tgs822_r0  / tgs822_rL);
#endif

    pref_.end();
}

// ─────────────────────────────────────────────────────────────────────────────
//  initTasks()
// ─────────────────────────────────────────────────────────────────────────────
void SmartCoffeeSystem::initTasks() {
    // Core 0: waveform Nextion
    xTaskCreatePinnedToCore(
        &SmartCoffeeSystem::core0TaskStatic,
        "Core0Task", 10000, NULL, 1, &t0H_, 0);

    // Core 1: scheduler utama (ADS + Serial)
    sch_.init();
    sch_.addTask(task_ads_);
    sch_.addTask(task_serial_);
    task_ads_.enable();
    task_serial_.enable();

    pcSerial.println("{\"info\":\"Sistem siap. Kirim #start; untuk mulai akuisisi.\"}");
}

// =============================================================================
//  ACQUISITION STATE MACHINE
// =============================================================================

void SmartCoffeeSystem::startAcquisition() {
    // Reset semua counter
    acq_cycle_         = 1;
    acq_sample_idx_    = 0;
    acq_total_samples_ = 0;
    memset(feat_sum_, 0, sizeof(feat_sum_));
    memset(feat_max_, 0, sizeof(feat_max_));
    feat_count_ = 0;

    acq_state_          = AcqState::COLLECTING;
    acq_phase_start_ms_ = millis();
    setAcquisitionActuators();

    // Kirim event START ke PC
    StaticJsonDocument<192> j;
    j["event"]        = "ACQ_START";
    j["phase"]        = acqStateName();
    j["cycle"]        = acq_cycle_;
    j["cycles_total"] = ACQ_REPETITIONS;
    j["collect_s"]    = ACQ_COLLECTION_SECONDS;
    j["purge_s"]      = ACQ_PURGE_SECONDS;
    j["total_samples_expected"] = ACQ_COLLECTION_SECONDS * ACQ_REPETITIONS;
    serializeJson(j, pcSerial);
    pcSerial.print("\n");
}

void SmartCoffeeSystem::stopAcquisition() {
    acq_state_      = AcqState::IDLE;
    acq_cycle_      = 0;
    acq_sample_idx_ = 0;
    setAcquisitionActuators();
    pcSerial.println("{\"event\":\"ACQ_STOP\",\"phase\":\"idle\"}");
}

// Dipanggil setiap detik dari adsCallback() SEBELUM emit JSON
void SmartCoffeeSystem::processAcquisitionState() {
    if (acq_state_ == AcqState::IDLE || acq_state_ == AcqState::COMPLETE) return;

    unsigned long elapsed_ms = millis() - acq_phase_start_ms_;

    if (acq_state_ == AcqState::COLLECTING) {
        // Akumulasi fitur untuk inferensi on-device
        feat_sum_[0] += adc_mq135_;   feat_max_[0] = max(feat_max_[0], adc_mq135_);
        feat_sum_[1] += adc_mq136_;   feat_max_[1] = max(feat_max_[1], adc_mq136_);
        feat_sum_[2] += adc_mq137_;   feat_max_[2] = max(feat_max_[2], adc_mq137_);
        feat_sum_[3] += adc_mq138_;   feat_max_[3] = max(feat_max_[3], adc_mq138_);
        feat_sum_[4] += adc_mq2_;     feat_max_[4] = max(feat_max_[4], adc_mq2_);
        feat_sum_[5] += adc_mq3_;     feat_max_[5] = max(feat_max_[5], adc_mq3_);
        feat_sum_[6] += adc_tgs822_;  feat_max_[6] = max(feat_max_[6], adc_tgs822_);
        feat_sum_[7] += adc_tgs2620_; feat_max_[7] = max(feat_max_[7], adc_tgs2620_);
        feat_count_++;

        if (elapsed_ms >= (unsigned long)ACQ_COLLECTION_SECONDS * 1000UL) {
            // Transisi → PURGING
            acq_state_          = AcqState::PURGING;
            acq_phase_start_ms_ = millis();
            acq_sample_idx_     = 0;
            setAcquisitionActuators();

            StaticJsonDocument<96> j;
            j["event"] = "PHASE_CHANGE";
            j["cycle"] = acq_cycle_;
            j["phase"] = acqStateName();
            serializeJson(j, pcSerial); pcSerial.print("\n");
        }
    }
    else if (acq_state_ == AcqState::PURGING) {
        if (elapsed_ms >= (unsigned long)ACQ_PURGE_SECONDS * 1000UL) {
            if (acq_cycle_ < ACQ_REPETITIONS) {
                // Transisi → COLLECTING (siklus berikutnya)
                acq_cycle_++;
                acq_state_          = AcqState::COLLECTING;
                acq_phase_start_ms_ = millis();
                acq_sample_idx_     = 0;
                setAcquisitionActuators();

                StaticJsonDocument<96> j;
                j["event"] = "PHASE_CHANGE";
                j["cycle"] = acq_cycle_;
                j["phase"] = acqStateName();
                serializeJson(j, pcSerial); pcSerial.print("\n");
            } else {
                // Semua siklus selesai → COMPLETE
                acq_state_ = AcqState::COMPLETE;
                setAcquisitionActuators();   // matikan semua aktuator
                printAcquisitionSummary();
                doInference();               // inferensi TinyML on-device
                acq_state_ = AcqState::IDLE;
            }
        }
    }
}

void SmartCoffeeSystem::setAcquisitionActuators() {
    switch (acq_state_) {
        case AcqState::COLLECTING:
            // Pompa ON + valve ke arah sampel kopi
            ledcWrite(LEDC_CHAN_PWM1, 255);   // valve ON
            ledcWrite(LEDC_CHAN_PWM2, 255);   // pompa ON
            break;

        case AcqState::PURGING:
            // Pompa ON + valve ke arah udara bebas (baseline sensor)
            ledcWrite(LEDC_CHAN_PWM1,   0);   // valve OFF (arah udara bebas)
            ledcWrite(LEDC_CHAN_PWM2, 255);   // pompa ON
            break;

        default:  // IDLE / COMPLETE
            ledcWrite(LEDC_CHAN_PWM1, 0);
            ledcWrite(LEDC_CHAN_PWM2, 0);
            break;
    }
}

const char* SmartCoffeeSystem::acqStateName() const {
    switch (acq_state_) {
        case AcqState::COLLECTING: return "collecting";
        case AcqState::PURGING:    return "purging";
        case AcqState::COMPLETE:   return "complete";
        default:                   return "idle";
    }
}

void SmartCoffeeSystem::printAcquisitionSummary() {
    StaticJsonDocument<128> j;
    j["event"]         = "ACQ_COMPLETE";
    j["cycles"]        = ACQ_REPETITIONS;
    j["total_samples"] = acq_total_samples_;
    j["feat_count"]    = feat_count_;
    serializeJson(j, pcSerial);
    pcSerial.print("\n");
}

// ─────────────────────────────────────────────────────────────────────────────
//  doInference() – Klasifikasi Tingkat Roasting On-Device (TinyML)
//
//  Fitur yang digunakan (16 nilai):
//    [mean_mq135, mean_mq136, mean_mq137, mean_mq138,
//     mean_mq2,   mean_mq3,   mean_tgs822, mean_tgs2620,
//     max_mq135,  max_mq136,  max_mq137,  max_mq138,
//     max_mq2,    max_mq3,    max_tgs822,  max_tgs2620]
//
//  Urutan ini harus sama persis dengan feature_cols di 4_train_rf.py
// ─────────────────────────────────────────────────────────────────────────────
void SmartCoffeeSystem::doInference() {
#if USE_ON_DEVICE_INFERENCE
    if (feat_count_ == 0) {
        pcSerial.println("{\"event\":\"INFERENCE\",\"error\":\"no collecting data\"}");
        return;
    }

    // Bangun vektor fitur (mean + max per sensor = 16 fitur)
    float features[16] = {
        (float)(feat_sum_[0] / feat_count_),  // mean_mq135
        (float)(feat_sum_[1] / feat_count_),  // mean_mq136
        (float)(feat_sum_[2] / feat_count_),  // mean_mq137
        (float)(feat_sum_[3] / feat_count_),  // mean_mq138
        (float)(feat_sum_[4] / feat_count_),  // mean_mq2
        (float)(feat_sum_[5] / feat_count_),  // mean_mq3
        (float)(feat_sum_[6] / feat_count_),  // mean_tgs822
        (float)(feat_sum_[7] / feat_count_),  // mean_tgs2620
        (float)feat_max_[0],                  // max_mq135
        (float)feat_max_[1],                  // max_mq136
        (float)feat_max_[2],                  // max_mq137
        (float)feat_max_[3],                  // max_mq138
        (float)feat_max_[4],                  // max_mq2
        (float)feat_max_[5],                  // max_mq3
        (float)feat_max_[6],                  // max_tgs822
        (float)feat_max_[7],                  // max_tgs2620
    };

    Eloquent::ML::Port::RandomForest classifier;
    const char* label = classifier.predictLabel(features);

    StaticJsonDocument<128> j;
    j["event"]      = "INFERENCE";
    j["result"]     = label;          // "light" / "medium" / "dark"
    j["feat_count"] = feat_count_;
    serializeJson(j, pcSerial);
    pcSerial.print("\n");

#else
    pcSerial.println("{\"event\":\"INFERENCE\",\"result\":\"N/A\",\"info\":\"Set USE_ON_DEVICE_INFERENCE=1 dan sertakan model_rf.h\"}");
#endif
}

// =============================================================================
//  SERIAL COMMAND PARSING
// =============================================================================

void SmartCoffeeSystem::processCommand(const String& cmd) {
    if (cmd == "#start") {
        if (acq_state_ == AcqState::IDLE) {
            startAcquisition();
        } else {
            pcSerial.println("{\"warn\":\"Akuisisi sudah berjalan. Kirim #stop; terlebih dahulu.\"}");
        }
    }
    else if (cmd == "#stop") {
        stopAcquisition();
    }
    // Forward command tampilan status roasting ke Nextion
    else {
        struct { const char* cmd; const char* txt; uint32_t bco; }
        nexTable[] = {
            { "#preheat", "preheat", 64073 },
            { "#charge",  "charge",  3970  },
            { "#light",   "light",   62785 },
            { "#medium",  "medium",  62401 },
            { "#dark",    "dark",    35520 },
            { "#finish",  "finish",  3970  },
        };
        for (auto& e : nexTable) {
            if (cmd == e.cmd) {
                nexSerial.print("t8.txt=\""); nexSerial.print(e.txt); nexSerial.print("\"");
                nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
                nexSerial.print("t8.bco="); nexSerial.print(e.bco);
                nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
                break;
            }
        }
    }
}

void SmartCoffeeSystem::serialReadCallback() {
    while (pcSerial.available()) {
        char c = (char)pcSerial.read();

        if (m6r_buf_i_ == 0 && c != '#') continue;  // tunggu karakter '#' pertama

        if (c == ';' || m6r_buf_i_ >= 254) {
            m6r_buf_[m6r_buf_i_] = '\0';
            processCommand(String(m6r_buf_));
            m6r_buf_i_ = 0;
        } else {
            m6r_buf_[m6r_buf_i_++] = c;
        }
    }
}

// =============================================================================
//  ADS CALLBACK – baca semua sensor, kirim JSON ke PC
// =============================================================================
void SmartCoffeeSystem::adsCallback() {
    // ── 1. Baca ADC ──────────────────────────────────────────────────────────
    adc_mq135_   = ads1_.readADC(ADS1_CHAN_MQ135);
    adc_mq136_   = ads2_.readADC(ADS2_CHAN_MQ136);
    adc_mq137_   = ads1_.readADC(ADS1_CHAN_MQ137);
    adc_mq138_   = ads1_.readADC(ADS1_CHAN_MQ138);
    adc_mq2_     = ads2_.readADC(ADS2_CHAN_MQ2);
    adc_mq3_     = ads1_.readADC(ADS1_CHAN_MQ3);
    adc_tgs822_  = ads2_.readADC(ADS2_CHAN_TGS822);
    adc_tgs2620_ = ads2_.readADC(ADS2_CHAN_TGS2620);

    // ── 2. Hitung PPM (opsional) ──────────────────────────────────────────────
#if USE_PPM
    mq135_.setADC(adc_mq135_);
    mq135_.setA(605.18);  mq135_.setB(-3.937);  float mq135_co      = mq135_.readSensor();
    mq135_.setA(77.255);  mq135_.setB(-3.18);   float mq135_alcohol = mq135_.readSensor();
    mq135_.setA(110.47);  mq135_.setB(-2.862);  float mq135_co2     = mq135_.readSensor();
    mq135_.setA(44.947);  mq135_.setB(-3.445);  float mq135_toluen  = mq135_.readSensor();
    mq135_.setA(102.2);   mq135_.setB(-2.473);  float mq135_nh4     = mq135_.readSensor();
    mq135_.setA(34.668);  mq135_.setB(-3.369);  float mq135_aceton  = mq135_.readSensor();

    mq136_.setADC(adc_mq136_);
    mq136_.setA(503.34);  mq136_.setB(-3.774);  float mq136_co  = mq136_.readSensor();
    mq136_.setA(98.551);  mq136_.setB(-2.475);  float mq136_nh4 = mq136_.readSensor();
    mq136_.setA(36.737);  mq136_.setB(-3.536);  float mq136_h2s = mq136_.readSensor();

    mq137_.setADC(adc_mq137_);
    mq137_.setA(503.34);  mq137_.setB(-3.774);  float mq137_co      = mq137_.readSensor();
    mq137_.setA(98.551);  mq137_.setB(-2.475);  float mq137_ethanol = mq137_.readSensor();
    mq137_.setA(36.737);  mq137_.setB(-3.536);  float mq137_nh3     = mq137_.readSensor();

    mq138_.setADC(adc_mq138_);
    mq138_.setA(987.99);  mq138_.setB(-2.162);  float mq138_benzene = mq138_.readSensor();
    mq138_.setA(574.25);  mq138_.setB(-2.222);  float mq138_hexane  = mq138_.readSensor();
    mq138_.setA(36974);   mq138_.setB(-3.109);  float mq138_co      = mq138_.readSensor();
    mq138_.setA(3616.1);  mq138_.setB(-2.675);  float mq138_alcohol = mq138_.readSensor();
    mq138_.setA(658.71);  mq138_.setB(-2.168);  float mq138_propane = mq138_.readSensor();

    mq2_.setADC(adc_mq2_);
    mq2_.setA(987.99);    mq2_.setB(-2.162);    float mq2_h2      = mq2_.readSensor();
    mq2_.setA(574.25);    mq2_.setB(-2.222);    float mq2_lpg     = mq2_.readSensor();
    mq2_.setA(36974);     mq2_.setB(-3.109);    float mq2_co      = mq2_.readSensor();
    mq2_.setA(3616.1);    mq2_.setB(-2.675);    float mq2_alcohol = mq2_.readSensor();
    mq2_.setA(658.71);    mq2_.setB(-2.168);    float mq2_propane = mq2_.readSensor();

    mq3_.setADC(adc_mq3_);
    mq3_.setA(44771);     mq3_.setB(-3.245);    float  mq3_lpg     = mq3_.readSensor();
    mq3_.setA(65.8824);   mq3_.setB(-1.1578);   double mq3_ch4     = mq3_.readSensor();
    mq3_.setA(521853);    mq3_.setB(-3.821);    float  mq3_co      = mq3_.readSensor();
    mq3_.setA(0.3934);    mq3_.setB(-1.504);    float  mq3_alcohol = mq3_.readSensor();
    mq3_.setA(4.8387);    mq3_.setB(-2.68);     float  mq3_benzene = mq3_.readSensor();
    mq3_.setA(7585.3);    mq3_.setB(-2.849);    float  mq3_hexane  = mq3_.readSensor();

    tgs822_.setADC(adc_tgs822_);
    double tgs822_methane   = tgs822_.calculatePpm(adc_tgs822_, 801945,    -3.583947);
    float  tgs822_co        = tgs822_.calculatePpm(adc_tgs822_, 2966.6364, -2.417324);
    float  tgs822_isobutane = tgs822_.calculatePpm(adc_tgs822_, 1424.408,  -2.263743);
    float  tgs822_hexane    = tgs822_.calculatePpm(adc_tgs822_, 343.0545,  -1.763533);
    float  tgs822_benzene   = tgs822_.calculatePpm(adc_tgs822_, 353.6719,  -1.575331);
    float  tgs822_ethanol   = tgs822_.calculatePpm(adc_tgs822_, 282.5765,  -1.599635);
    float  tgs822_acetone   = tgs822_.calculatePpm(adc_tgs822_, 317.8024,  -1.270728);

    tgs2620_.setADC(adc_tgs2620_);
    float tgs2620_methane   = tgs2620_.calculatePpm(adc_tgs2620_, 24599.121, -2.1599);
    float tgs2620_co        = tgs2620_.calculatePpm(adc_tgs2620_, 1301.825,  -1.7327);
    float tgs2620_isobutane = tgs2620_.calculatePpm(adc_tgs2620_, 495.948,   -1.5260);
    float tgs2620_h2        = tgs2620_.calculatePpm(adc_tgs2620_, 334.361,   -1.8144);
    float tgs2620_ethanol   = tgs2620_.calculatePpm(adc_tgs2620_, 324.036,   -1.50063);
#endif

    // SHT31 dinonaktifkan sementara
    // float t = sht31_.readTemperature();
    // float h = sht31_.readHumidity();
    // if (isnan(t)) t = -99;
    // if (isnan(h)) h = -99;

    // ── 3. Update state machine (transisi fase, akumulasi fitur) ─────────────
    processAcquisitionState();
    acq_sample_idx_++;
    if (acq_state_ == AcqState::COLLECTING || acq_state_ == AcqState::PURGING) {
        acq_total_samples_++;
    }

    // ── 4. Bangun dan kirim JSON ──────────────────────────────────────────────
    // Gunakan buffer 2 KB (aman di heap ESP32 520 KB)
    StaticJsonDocument<2048> j;

    // Metadata akuisisi — selalu ada
    j["phase"]      = acqStateName();     // "idle"|"collecting"|"purging"
    j["cycle"]      = acq_cycle_;         // nomor siklus (0 = idle)
    j["sample_idx"] = acq_sample_idx_;    // indeks dalam fase saat ini
    j["timestamp"]  = millis();

    // ADC mentah
    j["adc_mq135"]   = adc_mq135_;
    j["adc_mq136"]   = adc_mq136_;
    j["adc_mq137"]   = adc_mq137_;
    j["adc_mq138"]   = adc_mq138_;
    j["adc_mq2"]     = adc_mq2_;
    j["adc_mq3"]     = adc_mq3_;
    j["adc_tgs822"]  = adc_tgs822_;
    j["adc_tgs2620"] = adc_tgs2620_;
    // j["temp"]        = t;       // SHT31 dinonaktifkan
    // j["humidity"]    = h;       // SHT31 dinonaktifkan

#if USE_PPM
    j["mq135_co"]      = mq135_co;
    j["mq135_alcohol"] = mq135_alcohol;
    j["mq135_co2"]     = mq135_co2;
    j["mq135_toluen"]  = mq135_toluen;
    j["mq135_nh4"]     = mq135_nh4;
    j["mq135_aceton"]  = mq135_aceton;

    j["mq136_co"]      = mq136_co;
    j["mq136_nh4"]     = mq136_nh4;
    j["mq136_h2s"]     = mq136_h2s;

    j["mq137_co"]      = mq137_co;
    j["mq137_ethanol"] = mq137_ethanol;
    j["mq137_nh3"]     = mq137_nh3;

    j["mq138_benzene"] = mq138_benzene;
    j["mq138_hexane"]  = mq138_hexane;
    j["mq138_co"]      = mq138_co;
    j["mq138_alcohol"] = mq138_alcohol;
    j["mq138_propane"] = mq138_propane;

    j["mq2_h2"]      = mq2_h2;
    j["mq2_lpg"]     = mq2_lpg;
    j["mq2_co"]      = mq2_co;
    j["mq2_alcohol"] = mq2_alcohol;
    j["mq2_propane"] = mq2_propane;

    j["mq3_lpg"]     = mq3_lpg;
    j["mq3_ch4"]     = mq3_ch4;
    j["mq3_co"]      = mq3_co;
    j["mq3_alcohol"] = mq3_alcohol;
    j["mq3_benzene"] = mq3_benzene;
    j["mq3_hexane"]  = mq3_hexane;

    j["tgs822_methane"]   = tgs822_methane;
    j["tgs822_co"]        = tgs822_co;
    j["tgs822_isobutane"] = tgs822_isobutane;
    j["tgs822_hexane"]    = tgs822_hexane;
    j["tgs822_benzene"]   = tgs822_benzene;
    j["tgs822_ethanol"]   = tgs822_ethanol;
    j["tgs822_acetone"]   = tgs822_acetone;

    j["tgs2620_methane"]   = tgs2620_methane;
    j["tgs2620_co"]        = tgs2620_co;
    j["tgs2620_isobutane"] = tgs2620_isobutane;
    j["tgs2620_h2"]        = tgs2620_h2;
    j["tgs2620_ethanol"]   = tgs2620_ethanol;
#endif

    serializeJson(j, pcSerial);
    pcSerial.print("\n");
}

// =============================================================================
//  NEXTION WAVEFORM (Core 0)
// =============================================================================
void SmartCoffeeSystem::graphCallback() {
#if USE_NEXTION_GRAPH
    sendWave(NEX_WAVE1_CID, NEX_WAVE1_CHAN_MQ135,   (int)(ADC16TO8 * adc_mq135_));
    sendWave(NEX_WAVE1_CID, NEX_WAVE1_CHAN_MQ136,   (int)(ADC16TO8 * adc_mq136_));
    sendWave(NEX_WAVE1_CID, NEX_WAVE1_CHAN_MQ137,   (int)(ADC16TO8 * adc_mq137_));
    sendWave(NEX_WAVE1_CID, NEX_WAVE1_CHAN_MQ138,   (int)(ADC16TO8 * adc_mq138_));
    sendWave(NEX_WAVE2_CID, NEX_WAVE2_CHAN_MQ2,     (int)(ADC16TO8 * adc_mq2_));
    sendWave(NEX_WAVE2_CID, NEX_WAVE2_CHAN_MQ3,     (int)(ADC16TO8 * adc_mq3_));
    sendWave(NEX_WAVE2_CID, NEX_WAVE2_CHAN_TGS822,  (int)(ADC16TO8 * adc_tgs822_));
    sendWave(NEX_WAVE2_CID, NEX_WAVE2_CHAN_TGS2620, (int)(ADC16TO8 * adc_tgs2620_));
#endif
}

void SmartCoffeeSystem::sendWave(int cid, int chan, int val) {
    if (val > 254) val = 254;
    String msg = "add " + String(cid) + "," + String(chan) + "," + String(val);
    nexSerial.print(msg);
    nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
    delay(50);
}

void SmartCoffeeSystem::core0Task(void* param) {
    for (;;) {
        graphCallback();
        delay(200);
    }
}

// =============================================================================
//  Entry points Arduino
// =============================================================================
SmartCoffeeSystem coffeeSystem;

void setup() { coffeeSystem.begin(); }
void loop()  { coffeeSystem.run();   }

// #include <Arduino.h>
// #include <Wire.h>
// #include "ADS1X15.h"

// #define I2C_ADDR_ADS2 0x49
// #define ADS_GAIN      0

// #define ADS2_CHAN_MQ2     0
// #define ADS2_CHAN_MQ136   1
// #define ADS2_CHAN_TGS822  2
// #define ADS2_CHAN_TGS2620 3

// ADS1115 ads2_(I2C_ADDR_ADS2);

// void setup() {
//     Serial.begin(115200);
//     delay(1000);
//     Serial.println("ADS2 only test: bypass ADS1");

//     Wire.begin();
//     if (!ads2_.isConnected()) {
//         Serial.println("{\"error\":\"ADS2 not found\"}");
//         while (true) {
//             delay(1000);
//         }
//     }

//     ads2_.setGain(ADS_GAIN);
//     Serial.println("{\"info\":\"ADS2 initialized\"}");
// }

// void loop() {
//     uint16_t v_mq2     = ads2_.readADC(ADS2_CHAN_MQ2);
//     uint16_t v_mq136   = ads2_.readADC(ADS2_CHAN_MQ136);
//     uint16_t v_tgs822  = ads2_.readADC(ADS2_CHAN_TGS822);
//     uint16_t v_tgs2620 = ads2_.readADC(ADS2_CHAN_TGS2620);

//     unsigned long ts = millis();
//     Serial.print("{\"timestamp\":");
//     Serial.print(ts);
//     Serial.print(",\"mq2\":");
//     Serial.print(v_mq2);
//     Serial.print(",\"mq136\":");
//     Serial.print(v_mq136);
//     Serial.print(",\"tgs822\":");
//     Serial.print(v_tgs822);
//     Serial.print(",\"tgs2620\":");
//     Serial.print(v_tgs2620);
//     Serial.println("}");

//     delay(1000);
// }