// #include <Arduino.h>
// #include <Wire.h>
// #include "ADS1X15.h"
// #include "MQUnifiedsensor.h"
// #include "TGS2620.h"

// #define I2C_ADDR_ADS1    0x48 // GND
// #define I2C_ADDR_ADS2    0x49 // VCC
// #define I2C_ADDR_SHT21   0x44
// // #define ADS_GAIN      0

// // #define ADS2_CHAN_MQ2     0
// // #define ADS2_CHAN_MQ136   1
// // #define ADS2_CHAN_TGS822  2
// // #define ADS2_CHAN_TGS2620 3
// #define ADS_GAIN          0 //6.144V
// #define ADS_VOLTAGE       6.144
// #define ADS_ADC           16
// #define ADS1_CHAN_MQ137   0
// #define ADS1_CHAN_MQ3     1
// #define ADS1_CHAN_MQ138   2
// #define ADS1_CHAN_MQ135   3
// #define ADS2_CHAN_MQ2     0
// #define ADS2_CHAN_MQ136   1
// #define ADS2_CHAN_TGS822  2
// #define ADS2_CHAN_TGS2620 3

// ADS1115 ads1(I2C_ADDR_ADS1);
// ADS1115 ads2(I2C_ADDR_ADS2);

// // Adafruit_SHT31 sht31 = Adafruit_SHT31();

// MQUnifiedsensor mq135 ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-135");
// MQUnifiedsensor mq136 ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-136");
// MQUnifiedsensor mq137 ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-137");
// MQUnifiedsensor mq138 ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-138");
// MQUnifiedsensor mq2   ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-2");
// MQUnifiedsensor mq3   ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-3");
// TGS2620 tgs2620;
// TGS2620 tgs822; // rumus tgs2620 sm tgs822 sama, beda a b

// uint16_t adc_mq135   = 0;
// uint16_t adc_mq136   = 0;
// uint16_t adc_mq137   = 0;
// uint16_t adc_mq138   = 0;
// uint16_t adc_mq2     = 0;
// uint16_t adc_mq3     = 0;
// uint16_t adc_tgs822  = 0;
// uint16_t adc_tgs2620 = 0;


// void setup() {
//     Serial.begin(115200);
//     delay(1000);
//     Serial.println("ADS2 only test: bypass ADS1");

//     Wire.begin();
//     if (!ads1_.isConnected()) {
//         Serial.println("{\"error\":\"ADS2 ga ada\"}");
//         while (true) {
//             delay(1000);
//         }
//     }

//     ads1_.setGain(ADS_GAIN);
//     Serial.println("{\"info\":\"ADS2 initialized\"}");
// }

// void loop() {
//     // uint16_t v_mq2     = ads2_.readADC(ADS2_CHAN_MQ2);
//     // uint16_t v_mq136   = ads2_.readADC(ADS2_CHAN_MQ136);
//     // uint16_t v_tgs822  = ads2_.readADC(ADS2_CHAN_TGS822);
//     // uint16_t v_tgs2620 = ads2_.readADC(ADS2_CHAN_TGS2620);
//     // adc_mq135   = ads1.readADC(ADS1_CHAN_MQ135);
//     // adc_mq136   = ads2.readADC(ADS2_CHAN_MQ136);
//     // adc_mq137   = ads1.readADC(ADS1_CHAN_MQ137);
//     // adc_mq138   = ads1.readADC(ADS1_CHAN_MQ138);
//     // adc_mq2     = ads2.readADC(ADS2_CHAN_MQ2);
//     // adc_mq3     = ads1.readADC(ADS1_CHAN_MQ3);
//     // adc_tgs822  = ads2.readADC(ADS2_CHAN_TGS822);
//     // adc_tgs2620 = ads2.readADC(ADS2_CHAN_TGS2620);
//     adc_mq135   = ads1.readADC(ADS1_CHAN_MQ135);
//     adc_mq136   = ads2.readADC(ADS2_CHAN_MQ136);
//     adc_mq137   = ads1.readADC(ADS1_CHAN_MQ137);
//     adc_mq138   = ads1.readADC(ADS1_CHAN_MQ138);
//     adc_mq2     = ads2.readADC(ADS2_CHAN_MQ2);
//     adc_mq3     = ads1.readADC(ADS1_CHAN_MQ3);
//     adc_tgs822  = ads2.readADC(ADS2_CHAN_TGS822);
//     adc_tgs2620 = ads2.readADC(ADS2_CHAN_TGS2620);
//     // uint16_t adc_mq135   = 0;
//     // uint16_t adc_mq136   = 0;
//     // uint16_t adc_mq137   = 0;
//     // uint16_t adc_mq138   = 0;
//     // uint16_t adc_mq2     = 0;
//     // uint16_t adc_mq3     = 0;
//     // uint16_t adc_tgs822  = 0;
//     // uint16_t adc_tgs2620 = 0;

//     unsigned long ts = millis();
//     Serial.print("{\"timestamp\":");
//     Serial.print(ts);
//     Serial.print(",\"mq135\":");
//     Serial.print(adc_mq135);
//     Serial.print(",\"mq136\":");
//     Serial.print(adc_mq136);
//     Serial.print(",\"mq137\":");
//     Serial.print(adc_mq137);
//     Serial.print(",\"mq138\":");
//     Serial.print(adc_mq138);
//     Serial.print(",\"mq2\":");
//     Serial.print(adc_mq2);
//     Serial.print(",\"adc_mq3\":");
//     Serial.print(adc_mq3);
//     Serial.print(",\"tgs822\":");
//     Serial.print(adc_tgs822);
//     Serial.print(",\"tgs2620\":");
//     Serial.print(adc_tgs2620);
//     Serial.println("}");

//     delay(1000);
// }


#include <Arduino.h>
#include <Wire.h>
#include "ADS1X15.h"
#include "MQUnifiedsensor.h"
#include "TGS2620.h"

#define I2C_ADDR_ADS1    0x48 // GND
#define I2C_ADDR_ADS2    0x49 // VCC
#define I2C_ADDR_SHT21   0x44

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

ADS1115 ads1(I2C_ADDR_ADS1);
ADS1115 ads2(I2C_ADDR_ADS2);

MQUnifiedsensor mq135 ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-135");
MQUnifiedsensor mq136 ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-136");
MQUnifiedsensor mq137 ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-137");
MQUnifiedsensor mq138 ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-138");
MQUnifiedsensor mq2   ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-2");
MQUnifiedsensor mq3   ("ESP32", ADS_VOLTAGE, ADS_ADC, 0, "MQ-3");
TGS2620 tgs2620;
TGS2620 tgs822; // rumus tgs2620 sm tgs822 sama, beda a b

uint16_t adc_mq135   = 0;
uint16_t adc_mq136   = 0;
uint16_t adc_mq137   = 0;
uint16_t adc_mq138   = 0;
uint16_t adc_mq2     = 0;
uint16_t adc_mq3     = 0;
uint16_t adc_tgs822  = 0;
uint16_t adc_tgs2620 = 0;

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("ADS1 + ADS2 test");

    Wire.begin();

    // ADS1 (0x48)
    if (!ads1.begin()) {
        Serial.println("{\"error\":\"ADS1 gagal begin (cek wiring/alamat 0x48)\"}");
        while (true) { delay(1000); }
    }
    if (!ads1.isConnected()) {
        Serial.println("{\"error\":\"ADS1 CAPEK, AKU JUGA CAPEK BINGUNG GATAU KENAPA BISA ERORR BROUU\"}");
        while (true) { delay(1000); }
    }
    ads1.setGain(ADS_GAIN);

    // ADS2 (0x49)
    if (!ads2.begin()) {
        Serial.println("{\"error\":\"ADS2 gagal begin (cek wiring/alamat 0x49)\"}");
        while (true) { delay(1000); }
    }
    if (!ads2.isConnected()) {
        Serial.println("{\"error\":\"ADS2 ga ada\"}");
        while (true) { delay(1000); }
    }
    ads2.setGain(ADS_GAIN);

    Serial.println("{\"info\":\"ADS1 & ADS2 initialized\"}");
}

void loop() {
    adc_mq135   = ads1.readADC(ADS1_CHAN_MQ135);
    adc_mq137   = ads1.readADC(ADS1_CHAN_MQ137);
    adc_mq138   = ads1.readADC(ADS1_CHAN_MQ138);
    adc_mq3     = ads1.readADC(ADS1_CHAN_MQ3);
    adc_mq2     = ads2.readADC(ADS2_CHAN_MQ2);
    adc_mq136   = ads2.readADC(ADS2_CHAN_MQ136);
    adc_tgs822  = ads2.readADC(ADS2_CHAN_TGS822);
    adc_tgs2620 = ads2.readADC(ADS2_CHAN_TGS2620);

    unsigned long ts = millis();
    Serial.print("{\"timestamp\":");
    Serial.print(ts);
    Serial.print(",\"mq135\":");
    Serial.print(adc_mq135);
    Serial.print(",\"mq136\":");
    Serial.print(adc_mq136);
    Serial.print(",\"mq137\":");
    Serial.print(adc_mq137);
    Serial.print(",\"mq138\":");
    Serial.print(adc_mq138);
    Serial.print(",\"mq2\":");
    Serial.print(adc_mq2);
    Serial.print(",\"mq3\":");
    Serial.print(adc_mq3);
    Serial.print(",\"tgs822\":");
    Serial.print(adc_tgs822);
    Serial.print(",\"tgs2620\":");
    Serial.print(adc_tgs2620);
    Serial.println("}");

    delay(1000);
}
