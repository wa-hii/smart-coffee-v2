#include "Arduino.h"
#include <Wire.h>
#include <SPI.h>
#include "TaskScheduler.h"

// #include "Nextion.h"
#include "ArduinoJson.h"
#include "ADS1X15.h"
#include "Adafruit_SHT31.h"
#include <MQUnifiedsensor.h>
#include "TGS2602.h"
#include "TGS2600.h"

#define DEBUG 0

#define ADC16TO8 0.0038909912109375

#define I2C_ADDR_ADS1    0x48 // GND
#define I2C_ADDR_ADS2    0x49 // VCC

#define IO_INTERNAL_LED  2
#define IO_PWM1          4
#define IO_PWM2          5
#define LEDC_CHAN_PWM1   0
#define LEDC_CHAN_PWM2   1
#define LEDC_FREQ        5000
#define LEDC_RESO        8

#define ADS_GAIN          0 //6.144V
#define ADS1_CHAN_MQ135   0
#define ADS1_CHAN_MQ3     1
#define ADS1_CHAN_MQ136   2
#define ADS1_CHAN_MQ2     3
#define ADS2_CHAN_MQ137   0
#define ADS2_CHAN_MQ138   1
#define ADS2_CHAN_TGS822  2
#define ADS2_CHAN_TGS2620 3

#define NEX_BUTTON_START_PID 0
#define NEX_BUTTON_START_CID 4
#define NEX_BUTTON_START_NAME "b1"

#define NEX_BUTTON_STOP_PID 0
#define NEX_BUTTON_STOP_CID 3
#define NEX_BUTTON_STOP_NAME "b0"

#define NEX_BUTTON_RESET_PID 0
#define NEX_BUTTON_RESET_CID 5
#define NEX_BUTTON_RESET_NAME "b2"

#define NEX_WAVE1_PID 0
#define NEX_WAVE1_CID 1
#define NEX_WAVE1_NAME "s0"
#define NEX_WAVE2_PID 0
#define NEX_WAVE2_CID 2
#define NEX_WAVE2_NAME "s1"

#define NEX_WAVE1_CHAN_MQ135   0
#define NEX_WAVE1_CHAN_MQ136   1
#define NEX_WAVE1_CHAN_MQ137   2
#define NEX_WAVE1_CHAN_MQ138   3
#define NEX_WAVE2_CHAN_MQ2     0
#define NEX_WAVE2_CHAN_MQ3     1
#define NEX_WAVE2_CHAN_TGS822  2
#define NEX_WAVE2_CHAN_TGS2620 3

#define TASK_INTERVAL_MS_ADS 1
#define TASK_INTERVAL_MS_NEX 10

bool is_run = true;

// TaskHandle_t t0H;
Scheduler sch;

// NexButton button_start = NexButton(NEX_BUTTON_START_PID, NEX_BUTTON_START_CID, NEX_BUTTON_START_NAME);
// NexButton button_stop  = NexButton(NEX_BUTTON_STOP_PID, NEX_BUTTON_STOP_CID, NEX_BUTTON_STOP_NAME);
// NexButton button_reset = NexButton(NEX_BUTTON_RESET_PID, NEX_BUTTON_RESET_CID, NEX_BUTTON_RESET_NAME);
// NexWaveform wave1 = NexWaveform(NEX_WAVE1_PID, NEX_WAVE1_CID, NEX_WAVE1_NAME);
// NexWaveform wave2 = NexWaveform(NEX_WAVE2_PID, NEX_WAVE2_CID, NEX_WAVE2_NAME);

// NexTouch *nex_listen_list[] = {
//     &button_reset,
//     &button_start,
//     &button_stop,
//     NULL
// };

void buttonStartCb(void*);
void buttonStopCb(void*);
void buttonResetCb(void*);

ADS1115 ads1(I2C_ADDR_ADS1);
ADS1115 ads2(I2C_ADDR_ADS2);
Adafruit_SHT31 sht31 = Adafruit_SHT31();
MQUnifiedsensor MQ135("ESP", 6.144, 16, 1, "MQ-135");
MQUnifiedsensor MQ136("ESP", 6.144, 16, 1, "MQ-136");
MQUnifiedsensor MQ137("ESP", 6.144, 16, 1, "MQ-137");
MQUnifiedsensor MQ138("ESP", 6.144, 16, 1, "MQ-138");
MQUnifiedsensor MQ2("ESP", 6.144, 16, 1, "MQ-2");
MQUnifiedsensor MQ3("ESP", 6.144, 16, 1, "MQ-3");
TGS2602 tgs2602;

uint16_t adc_mq135   = 0;
uint16_t adc_mq136   = 0;
uint16_t adc_mq137   = 0;
uint16_t adc_mq138   = 0;
uint16_t adc_mq2     = 0;
uint16_t adc_mq3     = 0;
uint16_t adc_tgs822  = 0;
uint16_t adc_tgs2620 = 0;

void Core0Task(void*);

void fail();

void init_hardwares();
void init_check_sensors();
void init_tasks();

void adsCallback();
void nexCallback();

Task task_ads(TASK_INTERVAL_MS_ADS, TASK_FOREVER, &adsCallback);
Task task_nex(TASK_INTERVAL_MS_NEX, TASK_FOREVER, &nexCallback);


void setup()
{
    init_hardwares(); // GPIO and such
    init_check_sensors(); // Initial check for sensors
    init_tasks();
}

void loop() 
{
    sch.execute();
}


void Core0Task(void* vParam)
{
    String message = "";
    for(;;)
    {
        if(Serial.available() > 0){
            while(Serial.available() > 0)
            {
                message += Serial.read();
            }
            Serial.println(message);
            message = "";
        }
        Serial.println("hello");
        sleep(1000);
    }
}

void fail()
{
    while(1){
        Serial.println("error");
        sleep(1000);
    }
}

void init_hardwares()
{
    ledcSetup(LEDC_CHAN_PWM1, LEDC_FREQ, LEDC_RESO);
    ledcSetup(LEDC_CHAN_PWM2, LEDC_FREQ, LEDC_RESO);

    ledcAttachPin(IO_PWM1, LEDC_CHAN_PWM1);
    ledcAttachPin(IO_PWM2, LEDC_CHAN_PWM2);

    // nexInit();
    // button_start.attachPush(buttonStartCb);
    // button_stop.attachPush(buttonStopCb);
    // button_reset.attachPush(buttonResetCb);
    ledcWrite(LEDC_CHAN_PWM1, 245);
    ledcWrite(LEDC_CHAN_PWM2, 245);

    Wire.begin();
    Serial.begin(9600);
}

void init_check_sensors()
{
    if(!ads1.isConnected()){
        Serial.println("{\"error\" : \"ADS 1 ERROR!\"}");
        fail();
    }

    if(!ads2.isConnected()){
        Serial.println("{\"error\" : \"ADS 2 ERROR!\"}");
        fail();
    }

    ads1.setGain(ADS_GAIN);
    ads2.setGain(ADS_GAIN);

    MQ135.setRegressionMethod(1);
    MQ136.setRegressionMethod(1);
    MQ137.setRegressionMethod(1);
    MQ138.setRegressionMethod(1);
    MQ2.setRegressionMethod(1);
    MQ3.setRegressionMethod(1);
}

void init_tasks()
{
    // xTaskCreatePinnedToCore(
    //     Core0Task,   
    //     "Core0Task", 
    //     10000,    
    //     NULL,     
    //     1,        
    //     &t0H,     
    //     0);
    
    
    sch.init();
    sch.addTask(task_ads);
    // sch.addTask(task_nex);
    task_ads.enable();
    // task_nex.enable();
}

void adsCallback()
{
    // sample sensors
    adc_mq135   = ads1.readADC(ADS1_CHAN_MQ135);
    adc_mq136   = ads1.readADC(ADS1_CHAN_MQ136);
    adc_mq2     = ads1.readADC(ADS1_CHAN_MQ2);
    adc_mq3     = ads1.readADC(ADS1_CHAN_MQ3);
    adc_mq137   = ads2.readADC(ADS2_CHAN_MQ137);
    adc_mq138   = ads2.readADC(ADS2_CHAN_MQ138);
    adc_tgs822  = ads2.readADC(ADS2_CHAN_TGS822);
    adc_tgs2620 = ads2.readADC(ADS2_CHAN_TGS2620);

    // update graphs in nextion
    // wave1.addValue(NEX_WAVE1_CHAN_MQ135,   ADC16TO8 * adc_mq135);
    // wave1.addValue(NEX_WAVE1_CHAN_MQ136,   ADC16TO8 * adc_mq136);
    // wave1.addValue(NEX_WAVE1_CHAN_MQ137,   ADC16TO8 * adc_mq137);
    // wave1.addValue(NEX_WAVE1_CHAN_MQ138,   ADC16TO8 * adc_mq138);
    // wave2.addValue(NEX_WAVE2_CHAN_MQ2,     ADC16TO8 * adc_mq2);
    // wave2.addValue(NEX_WAVE2_CHAN_MQ3,     ADC16TO8 * adc_mq3);
    // wave2.addValue(NEX_WAVE2_CHAN_TGS822,  ADC16TO8 * adc_tgs822);
    // wave2.addValue(NEX_WAVE2_CHAN_TGS2620, ADC16TO8 * adc_tgs2620);

    // send data to m6
    const int sensor_json_cap = JSON_OBJECT_SIZE(8);
    StaticJsonDocument<sensor_json_cap> sensor_json;

    sensor_json["adc_mq135"]   = adc_mq135;
    sensor_json["adc_mq136"]   = adc_mq136;
    sensor_json["adc_mq137"]   = adc_mq137;
    sensor_json["adc_mq138"]   = adc_mq138;
    sensor_json["adc_mq2"]     = adc_mq2;
    sensor_json["adc_mq3"]     = adc_mq3;
    sensor_json["adc_tgs822"]  = adc_tgs822;
    sensor_json["adc_tgs2620"] = adc_tgs2620;

    serializeJson(sensor_json, Serial);
    Serial.print("\n");
}

void nexCallback()
{
    // nexLoop(nex_listen_list);
}

// int pwm = 0;
// const int inc = 25;

// void buttonStartCb(void *ptr)
// {
//   Serial.println("START");
//   if(pwm < 250) pwm += inc;
//   ledcWrite(LEDC_CHAN_PWM1, pwm);
// }

// void buttonStopCb(void *ptr)
// {
//   Serial.println("STOP");
//   if(pwm > 0) pwm -= inc;
//   ledcWrite(LEDC_CHAN_PWM1, pwm);
// }

// void buttonResetCb(void *ptr)
// {
//   Serial.println("RESET");
//   pwm = 0;
//   ledcWrite(LEDC_CHAN_PWM1, pwm);
// }