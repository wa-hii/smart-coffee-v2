// INISIASI LIBRARY YANG DIGUNAKAN
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Preferences.h>
#include "TaskScheduler.h"
#include "ArduinoJson.h"
#include "ADS1X15.h"
#include "Adafruit_SHT31.h"
#include "MQUnifiedsensor.h"
#include "TGS2620.h"

#define DEBUG 0
#define PREF_NAMESPACE_ENOSE_R0 "enose_r0"
#define ADC16TO8 0.0038909912109375

#define I2C_ADDR_ADS1    0x48 // GND
#define I2C_ADDR_ADS2    0x49 // VCC
#define I2C_ADDR_SHT21   0x44

#define IO_INTERNAL_LED  2
#define IO_PWM1          27   // valve: (L)IN_VLV0
#define IO_PWM2          23   // pump : (L)SC_IN
#define LEDC_CHAN_PWM1   0
#define LEDC_CHAN_PWM2   1
#define LEDC_FREQ        5000
#define LEDC_RESO        8

#define ADS_GAIN          0 //6.144V
#define ADS_VOLTAGE       6.144
#define ADS_ADC           16
#define ADS1_CHAN_MQ137   0
#define ADS1_CHAN_MQ3     1
#define ADS1_CHAN_MQ138   2
#define ADS1_CHAN_MQ135   3
#define ADS2_CHAN_MQ2     0
#define ADS2_CHAN_MQ136   1
#define ADS2_CHAN_TGS822  2
#define ADS2_CHAN_TGS2620 3

#define NEX_BUTTON_RESET_PID 0
#define NEX_BUTTON_RESET_CID 6
#define NEX_BUTTON_RESET_NAME "b2"

#define NEX_WAVE1_PID 0
#define NEX_WAVE1_CID 2
#define NEX_WAVE1_NAME "s0"
#define NEX_WAVE2_PID 0
#define NEX_WAVE2_CID 3
#define NEX_WAVE2_NAME "s1"

#define NEX_WAVE1_CHAN_MQ135   0
#define NEX_WAVE1_CHAN_MQ136   1
#define NEX_WAVE1_CHAN_MQ137   2
#define NEX_WAVE1_CHAN_MQ138   3
#define NEX_WAVE2_CHAN_MQ2     0
#define NEX_WAVE2_CHAN_MQ3     1
#define NEX_WAVE2_CHAN_TGS822  2
#define NEX_WAVE2_CHAN_TGS2620 3

#define TASK_INTERVAL_MS_ADS    1
#define TASK_INTERVAL_MS_NEX    20
#define TASK_INTERVAL_MS_GRAPH  20
#define TASK_INTERVAL_MS_M6READ 20

#define USE_NEXTION_GRAPH 0
#define IS_CALIBRATING_GAS_SENSOR 0
#define USE_PPM 1

#define pcSerial Serial
#define nexSerial Serial2

namespace ROASTING_LEVEL {
    enum { CHARGE, LIGHT, MEDIUM, DARK };
}

class SmartCoffeeSystem {
public:
    SmartCoffeeSystem();
    void begin();
    void run();

private:
    static SmartCoffeeSystem* instance_;

    static void adsCallbackStatic();
    static void graphCallbackStatic();
    static void m6ReadCallbackStatic();
    static void core0TaskStatic(void* param);

    void fail();
    void initHardwares();
    void initCheckSensors();
    void initTasks();
    void adsCallback();
    void graphCallback();
    void m6ReadCallback();
    void processM6ReadData(String data);
    void sendWave(int cid, int chan, int val);
    void buttonResetCb(void* ptr);
    void nexCallback();
    void core0Task(void* param);

    Preferences pref_;
    TaskHandle_t t0H_{};
    Scheduler sch_;
    Task task_ads_;
    Task task_graph_;
    Task task_m6read_;

    ADS1115 ads1_;
    ADS1115 ads2_;
    Adafruit_SHT31 sht31_;

    MQUnifiedsensor mq135_;
    MQUnifiedsensor mq136_;
    MQUnifiedsensor mq137_;
    MQUnifiedsensor mq138_;
    MQUnifiedsensor mq2_;
    MQUnifiedsensor mq3_;
    TGS2620 tgs2620_;
    TGS2620 tgs822_;

    uint16_t adc_mq135_ = 0;
    uint16_t adc_mq136_ = 0;
    uint16_t adc_mq137_ = 0;
    uint16_t adc_mq138_ = 0;
    uint16_t adc_mq2_ = 0;
    uint16_t adc_mq3_ = 0;
    uint16_t adc_tgs822_ = 0;
    uint16_t adc_tgs2620_ = 0;

    bool is_run_ = true;
    char m6r_buf_[1024]{};
    int m6r_buf_i_ = 0;
    char buf_[1024]{};
    int buf_i_ = 0;
};

SmartCoffeeSystem* SmartCoffeeSystem::instance_ = nullptr;

SmartCoffeeSystem::SmartCoffeeSystem()
    : task_ads_(TASK_INTERVAL_MS_ADS, TASK_FOREVER, &SmartCoffeeSystem::adsCallbackStatic),
      task_graph_(TASK_INTERVAL_MS_GRAPH, TASK_FOREVER, &SmartCoffeeSystem::graphCallbackStatic),
      task_m6read_(TASK_INTERVAL_MS_GRAPH, TASK_FOREVER, &SmartCoffeeSystem::m6ReadCallbackStatic),
      ads1_(I2C_ADDR_ADS1),
      ads2_(I2C_ADDR_ADS2),
      sht31_(),
      mq135_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-135"),
      mq136_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-136"),
      mq137_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-137"),
      mq138_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-138"),
      mq2_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-2"),
      mq3_("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-3"),
      tgs2620_(),
      tgs822_() {
    instance_ = this;
}

void SmartCoffeeSystem::begin() {
    initHardwares();
    initCheckSensors();
    initTasks();
}

void SmartCoffeeSystem::run() {
    sch_.execute();
}

void SmartCoffeeSystem::adsCallbackStatic() {
    if (instance_ != nullptr) {
        instance_->adsCallback();
    }
}

void SmartCoffeeSystem::graphCallbackStatic() {
    if (instance_ != nullptr) {
        instance_->graphCallback();
    }
}

void SmartCoffeeSystem::m6ReadCallbackStatic() {
    if (instance_ != nullptr) {
        instance_->m6ReadCallback();
    }
}

void SmartCoffeeSystem::core0TaskStatic(void* param) {
    if (instance_ != nullptr) {
        instance_->core0Task(param);
    }
}

void SmartCoffeeSystem::fail() {
    while (1) {
        pcSerial.println("{\"error\" : \"ERROR!\"}");
        delay(1000);
    }
}

void SmartCoffeeSystem::initHardwares() {
    ledcSetup(LEDC_CHAN_PWM1, LEDC_FREQ, LEDC_RESO);
    ledcSetup(LEDC_CHAN_PWM2, LEDC_FREQ, LEDC_RESO);

    ledcAttachPin(IO_PWM1, LEDC_CHAN_PWM1);
    ledcAttachPin(IO_PWM2, LEDC_CHAN_PWM2);

    ledcWrite(LEDC_CHAN_PWM1, 255);
    ledcWrite(LEDC_CHAN_PWM2, 255);

    Wire.begin();

    pcSerial.begin(115200);
    nexSerial.begin(9600);
}

void SmartCoffeeSystem::initCheckSensors() {
    if (!sht31_.begin(I2C_ADDR_SHT21)) {
        pcSerial.println("{\"error\" : \"SHT31 ERROR!\"}");
        fail();
    }

    if (sht31_.isHeaterEnabled()) {
        pcSerial.println("{\"info\" : \"SHT31 Heater Enabled!\"}");
    } else {
        pcSerial.println("{\"info\" : \"SHT31 Heater Disabled!\"}");
    }

    if (!ads1_.isConnected()) {
        pcSerial.println("{\"error\" : \"ADS 1 ERROR!\"}");
        fail();
    }

    if (!ads2_.isConnected()) {
        pcSerial.println("{\"error\" : \"ADS 2 ERROR!\"}");
        fail();
    }

    ads1_.setGain(ADS_GAIN);
    ads2_.setGain(ADS_GAIN);

    float mq135_rL = 20;
    float ratio_mq135_air = 3.6;
    mq135_.setRegressionMethod(1);
    mq135_.setRL(mq135_rL);

    float mq136_rL = 20;
    float ratio_mq136_air = 3.6;
    mq136_.setRegressionMethod(1);
    mq136_.setRL(mq136_rL);

    float mq137_rL = 20;
    float ratio_mq137_air = 3.6;
    mq137_.setRegressionMethod(1);
    mq137_.setRL(mq137_rL);

    float mq138_rL = 20;
    float ratio_mq138_air = 9.8;
    mq138_.setRegressionMethod(1);
    mq138_.setRL(mq138_rL);

    float mq2_rL = 20;
    float ratio_mq2_air = 9.83;
    mq2_.setRegressionMethod(1);
    mq2_.setRL(mq2_rL);

    float mq3_rL = 20;
    float ratio_mq3_air = 60;
    mq3_.setRegressionMethod(1);
    mq3_.setRL(mq3_rL);

    float tgs2620_rL = 20;
    float ratio_tgs2620_air = 21;
    tgs2620_.setRL(tgs2620_rL);
    tgs2620_.setRatioAir(ratio_tgs2620_air);

    float tgs822_rL = 20;
    float ratio_tgs822_air = 17;
    tgs822_.setRL(tgs822_rL);
    tgs822_.setRatioAir(ratio_tgs822_air);

    pref_.begin(PREF_NAMESPACE_ENOSE_R0, false);

#if IS_CALIBRATING_GAS_SENSOR
    pcSerial.println("{\"info\" : \"Calibrating gas sensors...\"}");

    float calc_r0 = 0;
    for (int i = 1; i <= 10; i++) {
        adc_mq135_ = ads1_.readADC(ADS1_CHAN_MQ135);
        mq135_.setADC(adc_mq135_);
        calc_r0 += mq135_.calibrate(ratio_mq135_air);
    }
    mq135_.setR0(calc_r0 / mq135_rL);
    pref_.putFloat("mq135", calc_r0);

    calc_r0 = 0;
    for (int i = 1; i <= 10; i++) {
        adc_mq136_ = ads2_.readADC(ADS2_CHAN_MQ136);
        mq136_.setADC(adc_mq136_);
        calc_r0 += mq136_.calibrate(ratio_mq136_air);
    }
    mq136_.setR0(calc_r0 / mq136_rL);
    pref_.putFloat("mq136", calc_r0);

    calc_r0 = 0;
    for (int i = 1; i <= 10; i++) {
        adc_mq137_ = ads1_.readADC(ADS1_CHAN_MQ137);
        mq137_.setADC(adc_mq137_);
        calc_r0 += mq137_.calibrate(ratio_mq137_air);
    }
    mq137_.setR0(calc_r0 / mq137_rL);
    pref_.putFloat("mq137", calc_r0);

    calc_r0 = 0;
    for (int i = 1; i <= 10; i++) {
        adc_mq138_ = ads1_.readADC(ADS1_CHAN_MQ138);
        mq138_.setADC(adc_mq138_);
        calc_r0 += mq138_.calibrate(ratio_mq138_air);
    }
    mq138_.setR0(calc_r0 / mq138_rL);
    pref_.putFloat("mq138", calc_r0);

    calc_r0 = 0;
    for (int i = 1; i <= 10; i++) {
        adc_mq2_ = ads2_.readADC(ADS2_CHAN_MQ2);
        mq2_.setADC(adc_mq2_);
        calc_r0 += mq2_.calibrate(ratio_mq2_air);
    }
    mq2_.setR0(calc_r0 / mq2_rL);
    pref_.putFloat("mq2", calc_r0);

    calc_r0 = 0;
    for (int i = 1; i <= 10; i++) {
        adc_mq3_ = ads1_.readADC(ADS1_CHAN_MQ3);
        mq3_.setADC(adc_mq3_);
        calc_r0 += mq3_.calibrate(ratio_mq3_air);
    }
    mq3_.setR0(calc_r0 / mq3_rL);
    pref_.putFloat("mq3", calc_r0);

    calc_r0 = 0;
    for (int i = 1; i <= 10; i++) {
        adc_tgs2620_ = ads2_.readADC(ADS2_CHAN_TGS2620);
        tgs2620_.setADC(adc_tgs2620_);
        calc_r0 += tgs2620_.calibrate(ratio_tgs2620_air);
    }
    tgs2620_.setR0(calc_r0 / tgs2620_rL);
    pref_.putFloat("tgs2620", calc_r0);

    calc_r0 = 0;
    for (int i = 1; i <= 10; i++) {
        adc_tgs822_ = ads2_.readADC(ADS2_CHAN_TGS822);
        tgs822_.setADC(adc_tgs822_);
        calc_r0 += tgs822_.calibrate(ratio_tgs822_air);
    }
    tgs822_.setR0(calc_r0 / tgs822_rL);
    pref_.putFloat("tgs822", calc_r0);

    pcSerial.println("{\"info\" : \"calibration done\"}");
#else
    float mq135_r0 = pref_.getFloat("mq135");
    float mq136_r0 = pref_.getFloat("mq136");
    float mq137_r0 = pref_.getFloat("mq137");
    float mq138_r0 = pref_.getFloat("mq138");
    float mq2_r0 = pref_.getFloat("mq2");
    float mq3_r0 = pref_.getFloat("mq3");
    float tgs2620_r0 = pref_.getFloat("tgs2620");
    float tgs822_r0 = pref_.getFloat("tgs822");

    if (mq135_r0 <= 0 || mq136_r0 <= 0 || mq137_r0 <= 0 || mq138_r0 <= 0 ||
        mq2_r0 <= 0 || mq3_r0 <= 0 || tgs2620_r0 <= 0 || tgs822_r0 <= 0) {
        pcSerial.println("{\"error\" : \"Gas sensors not calibrated yet. Set IS_CALIBRATING_GAS_SENSOR to 1, reflash once in clean air, then set it back to 0.\"}");
        fail();
    }

    mq135_.setR0(mq135_r0 / mq135_rL);
    mq136_.setR0(mq136_r0 / mq136_rL);
    mq137_.setR0(mq137_r0 / mq137_rL);
    mq138_.setR0(mq138_r0 / mq138_rL);
    mq2_.setR0(mq2_r0 / mq2_rL);
    mq3_.setR0(mq3_r0 / mq3_rL);
    tgs2620_.setR0(tgs2620_r0 / tgs2620_rL);
    tgs822_.setR0(tgs822_r0 / tgs822_rL);
#endif

    pref_.end();
}

void SmartCoffeeSystem::initTasks() {
    xTaskCreatePinnedToCore(
        &SmartCoffeeSystem::core0TaskStatic,
        "Core0Task",
        10000,
        NULL,
        1,
        &t0H_,
        0);

    sch_.init();
    sch_.addTask(task_ads_);
    sch_.addTask(task_m6read_);
    task_ads_.enable();
    task_m6read_.enable();
}

void SmartCoffeeSystem::adsCallback() {
    adc_mq135_ = ads1_.readADC(ADS1_CHAN_MQ135);
    adc_mq136_ = ads2_.readADC(ADS2_CHAN_MQ136);
    adc_mq137_ = ads1_.readADC(ADS1_CHAN_MQ137);
    adc_mq138_ = ads1_.readADC(ADS1_CHAN_MQ138);
    adc_mq2_ = ads2_.readADC(ADS2_CHAN_MQ2);
    adc_mq3_ = ads1_.readADC(ADS1_CHAN_MQ3);
    adc_tgs822_ = ads2_.readADC(ADS2_CHAN_TGS822);
    adc_tgs2620_ = ads2_.readADC(ADS2_CHAN_TGS2620);

    mq135_.setADC(adc_mq135_);
    mq135_.setA(605.18); mq135_.setB(-3.937);
    float mq135_co = mq135_.readSensor();
    mq135_.setA(77.255); mq135_.setB(-3.18);
    float mq135_alcohol = mq135_.readSensor();
    mq135_.setA(110.47); mq135_.setB(-2.862);
    float mq135_co2 = mq135_.readSensor();
    mq135_.setA(44.947); mq135_.setB(-3.445);
    float mq135_toluen = mq135_.readSensor();
    mq135_.setA(102.2); mq135_.setB(-2.473);
    float mq135_nh4 = mq135_.readSensor();
    mq135_.setA(34.668); mq135_.setB(-3.369);
    float mq135_aceton = mq135_.readSensor();

    mq136_.setADC(adc_mq136_);
    mq136_.setA(503.34); mq136_.setB(-3.774);
    float mq136_co = mq136_.readSensor();
    mq136_.setA(98.551); mq136_.setB(-2.475);
    float mq136_nh4 = mq136_.readSensor();
    mq136_.setA(36.737); mq136_.setB(-3.536);
    float mq136_h2s = mq136_.readSensor();

    mq137_.setADC(adc_mq137_);
    mq137_.setA(503.34); mq137_.setB(-3.774);
    float mq137_co = mq137_.readSensor();
    mq137_.setA(98.551); mq137_.setB(-2.475);
    float mq137_ethanol = mq137_.readSensor();
    mq137_.setA(36.737); mq137_.setB(-3.536);
    float mq137_nh3 = mq137_.readSensor();

    mq138_.setADC(adc_mq138_);
    mq138_.setA(987.99); mq138_.setB(-2.162);
    float mq138_benzene = mq138_.readSensor();
    mq138_.setA(574.25); mq138_.setB(-2.222);
    float mq138_hexane = mq138_.readSensor();
    mq138_.setA(36974); mq138_.setB(-3.109);
    float mq138_co = mq138_.readSensor();
    mq138_.setA(3616.1); mq138_.setB(-2.675);
    float mq138_alcohol = mq138_.readSensor();
    mq138_.setA(658.71); mq138_.setB(-2.168);
    float mq138_propane = mq138_.readSensor();

    mq2_.setADC(adc_mq2_);
    mq2_.setA(987.99); mq2_.setB(-2.162);
    float mq2_h2 = mq2_.readSensor();
    mq2_.setA(574.25); mq2_.setB(-2.222);
    float mq2_lpg = mq2_.readSensor();
    mq2_.setA(36974); mq2_.setB(-3.109);
    float mq2_co = mq2_.readSensor();
    mq2_.setA(3616.1); mq2_.setB(-2.675);
    float mq2_alcohol = mq2_.readSensor();
    mq2_.setA(658.71); mq2_.setB(-2.168);
    float mq2_propane = mq2_.readSensor();

    mq3_.setADC(adc_mq3_);
    mq3_.setA(44771); mq3_.setB(-3.245);
    float mq3_lpg = mq3_.readSensor();
    mq3_.setA(65.8824); mq3_.setB(-1.1578);
    double mq3_ch4 = mq3_.readSensor();
    mq3_.setA(521853); mq3_.setB(-3.821);
    float mq3_co = mq3_.readSensor();
    mq3_.setA(0.3934); mq3_.setB(-1.504);
    float mq3_alcohol = mq3_.readSensor();
    mq3_.setA(4.8387); mq3_.setB(-2.68);
    float mq3_benzene = mq3_.readSensor();
    mq3_.setA(7585.3); mq3_.setB(-2.849);
    float mq3_hexane = mq3_.readSensor();

    tgs822_.setADC(adc_tgs822_);
    double tgs822_methane = tgs822_.calculatePpm(adc_tgs822_, 801945, -3.583947);
    float tgs822_co = tgs822_.calculatePpm(adc_tgs822_, 2966.6364, -2.417324);
    float tgs822_isobutane = tgs822_.calculatePpm(adc_tgs822_, 1424.408, -2.263743);
    float tgs822_hexane = tgs822_.calculatePpm(adc_tgs822_, 343.0545, -1.763533);
    float tgs822_benzene = tgs822_.calculatePpm(adc_tgs822_, 353.6719, -1.575331);
    float tgs822_ethanol = tgs822_.calculatePpm(adc_tgs822_, 282.5765, -1.599635);
    float tgs822_acetone = tgs822_.calculatePpm(adc_tgs822_, 317.8024, -1.270728);

    tgs2620_.setADC(adc_tgs2620_);
    float tgs2620_methane = tgs2620_.calculatePpm(adc_tgs2620_, 24599.121, -2.1599);
    float tgs2620_co = tgs2620_.calculatePpm(adc_tgs2620_, 1301.825, -1.7327);
    float tgs2620_isobutane = tgs2620_.calculatePpm(adc_tgs2620_, 495.948, -1.5260);
    float tgs2620_h2 = tgs2620_.calculatePpm(adc_tgs2620_, 334.361, -1.8144);
    float tgs2620_ethanol = tgs2620_.calculatePpm(adc_tgs2620_, 324.036, -1.50063);

    float t = sht31_.readTemperature();
    float h = sht31_.readHumidity();
    if (isnan(t)) t = -99;
    if (isnan(h)) h = -99;

#if USE_PPM
#define SENSOR_DATA_SIZE 11 + 6 + 3 + 3 + 5 + 5 + 6 + 7 + 5
#else
#define SENSOR_DATA_SIZE 11
#endif

    const int sensor_json_cap = JSON_OBJECT_SIZE(SENSOR_DATA_SIZE);
    StaticJsonDocument<sensor_json_cap> sensor_json;

    sensor_json["timestamp"] = millis();
    sensor_json["adc_mq135"] = adc_mq135_;
    sensor_json["adc_mq136"] = adc_mq136_;
    sensor_json["adc_mq137"] = adc_mq137_;
    sensor_json["adc_mq138"] = adc_mq138_;
    sensor_json["adc_mq2"] = adc_mq2_;
    sensor_json["adc_mq3"] = adc_mq3_;
    sensor_json["adc_tgs822"] = adc_tgs822_;
    sensor_json["adc_tgs2620"] = adc_tgs2620_;
    sensor_json["temp"] = t;
    sensor_json["humidity"] = h;

#if USE_PPM
    sensor_json["mq135_co"] = mq135_co;
    sensor_json["mq135_alcohol"] = mq135_alcohol;
    sensor_json["mq135_co2"] = mq135_co2;
    sensor_json["mq135_toluen"] = mq135_toluen;
    sensor_json["mq135_nh4"] = mq135_nh4;
    sensor_json["mq135_aceton"] = mq135_aceton;

    sensor_json["mq136_co"] = mq136_co;
    sensor_json["mq136_nh4"] = mq136_nh4;
    sensor_json["mq136_h2s"] = mq136_h2s;

    sensor_json["mq137_co"] = mq137_co;
    sensor_json["mq137_ethanol"] = mq137_ethanol;
    sensor_json["mq137_nh3"] = mq137_nh3;

    sensor_json["mq138_benzene"] = mq138_benzene;
    sensor_json["mq138_hexane"] = mq138_hexane;
    sensor_json["mq138_co"] = mq138_co;
    sensor_json["mq138_alcohol"] = mq138_alcohol;
    sensor_json["mq138_propane"] = mq138_propane;

    sensor_json["mq2_h2"] = mq2_h2;
    sensor_json["mq2_lpg"] = mq2_lpg;
    sensor_json["mq2_co"] = mq2_co;
    sensor_json["mq2_alcohol"] = mq2_alcohol;
    sensor_json["mq2_propane"] = mq2_propane;

    sensor_json["mq3_lpg"] = mq3_lpg;
    sensor_json["mq3_ch4"] = mq3_ch4;
    sensor_json["mq3_co"] = mq3_co;
    sensor_json["mq3_alcohol"] = mq3_alcohol;
    sensor_json["mq3_benzene"] = mq3_benzene;
    sensor_json["mq3_hexane"] = mq3_hexane;

    sensor_json["tgs822_methane"] = tgs822_methane;
    sensor_json["tgs822_co"] = tgs822_co;
    sensor_json["tgs822_isobutane"] = tgs822_isobutane;
    sensor_json["tgs822_hexane"] = tgs822_hexane;
    sensor_json["tgs822_benzene"] = tgs822_benzene;
    sensor_json["tgs822_ethanol"] = tgs822_ethanol;
    sensor_json["tgs822_acetone"] = tgs822_acetone;

    sensor_json["tgs2620_methane"] = tgs2620_methane;
    sensor_json["tgs2620_co"] = tgs2620_co;
    sensor_json["tgs2620_isobutane"] = tgs2620_isobutane;
    sensor_json["tgs2620_h2"] = tgs2620_h2;
    sensor_json["tgs2620_ethanol"] = tgs2620_ethanol;
#endif

    serializeJson(sensor_json, pcSerial);
    pcSerial.print("\n");
}

void SmartCoffeeSystem::graphCallback() {
#if USE_NEXTION_GRAPH
    sendWave(NEX_WAVE1_CID, NEX_WAVE1_CHAN_MQ135, (int)(ADC16TO8 * adc_mq135_));
    sendWave(NEX_WAVE1_CID, NEX_WAVE1_CHAN_MQ136, (int)(ADC16TO8 * adc_mq136_));
    sendWave(NEX_WAVE1_CID, NEX_WAVE1_CHAN_MQ137, (int)(ADC16TO8 * adc_mq137_));
    sendWave(NEX_WAVE1_CID, NEX_WAVE1_CHAN_MQ138, (int)(ADC16TO8 * adc_mq138_));
    sendWave(NEX_WAVE2_CID, NEX_WAVE2_CHAN_MQ2, (int)(ADC16TO8 * adc_mq2_));
    sendWave(NEX_WAVE2_CID, NEX_WAVE2_CHAN_MQ3, (int)(ADC16TO8 * adc_mq3_));
    sendWave(NEX_WAVE2_CID, NEX_WAVE2_CHAN_TGS822, (int)(ADC16TO8 * adc_tgs822_));
    sendWave(NEX_WAVE2_CID, NEX_WAVE2_CHAN_TGS2620, (int)(ADC16TO8 * adc_tgs2620_));
#endif
}

void SmartCoffeeSystem::processM6ReadData(String data) {
    if (data == "#preheat") {
        nexSerial.print("t8.txt=\"preheat\"");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
        nexSerial.print("t8.bco=64073");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
    } else if (data == "#charge") {
        nexSerial.print("t8.txt=\"charge\"");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
        nexSerial.print("t8.bco=3970");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
    } else if (data == "#light") {
        nexSerial.print("t8.txt=\"light\"");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
        nexSerial.print("t8.bco=62785");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
    } else if (data == "#medium") {
        nexSerial.print("t8.txt=\"medium\"");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
        nexSerial.print("t8.bco=62401");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
    } else if (data == "#dark") {
        nexSerial.print("t8.txt=\"dark\"");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
        nexSerial.print("t8.bco=35520");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
    } else if (data == "#finish") {
        nexSerial.print("t8.txt=\"finish\"");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
        nexSerial.print("t8.bco=3970");
        nexSerial.write(0xFF); nexSerial.write(0xFF); nexSerial.write(0xFF);
    }
}

void SmartCoffeeSystem::m6ReadCallback() {
    if (pcSerial.available()) {
        while (pcSerial.available()) {
            m6r_buf_[m6r_buf_i_] = pcSerial.read();

            if (m6r_buf_i_ == 0 && m6r_buf_[m6r_buf_i_] != '#') {
                continue;
            }

            if (m6r_buf_[m6r_buf_i_] == ';' || m6r_buf_i_ >= 1023) {
                m6r_buf_[m6r_buf_i_] = '\0';
                processM6ReadData(String(m6r_buf_));
                m6r_buf_i_ = 0;
            } else {
                m6r_buf_i_++;
            }
        }
    }
}

void SmartCoffeeSystem::nexCallback() {
    // if (nexSerial.available()) {
    //     while (nexSerial.available()) {
    //         buf_[buf_i_] = nexSerial.read();
    //         if (buf_i_ == 0 && buf_[buf_i_] != '#') {
    //             continue;
    //         }
    //         if (buf_[buf_i_] == ';' || buf_i_ >= 1023) {
    //             buf_[buf_i_] = '\0';
    //             buf_i_ = 0;
    //         } else {
    //             buf_i_++;
    //         }
    //     }
    // }
}

void SmartCoffeeSystem::buttonResetCb(void* ptr) {
    pcSerial.println("OFF1");
}

void SmartCoffeeSystem::core0Task(void* param) {
    for (;;) {
        graphCallback();
        delay(200);
    }
}

void SmartCoffeeSystem::sendWave(int cid, int chan, int val) {
    if (val > 254) {
        val = 254;
    }

    String msg = "add " + String(cid) + "," + String(chan) + "," + String(val);
    nexSerial.print(msg);
    nexSerial.write(0xFF);
    nexSerial.write(0xFF);
    nexSerial.write(0xFF);
    delay(50);
}

SmartCoffeeSystem coffeeSystem;

void setup() {
    coffeeSystem.begin();
}

void loop() {
    coffeeSystem.run();
}