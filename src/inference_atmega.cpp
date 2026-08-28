// inference_atmega.cpp — Implementasi Inference untuk ATmega2560
// 
// CATATAN: Untuk ATmega, model RF HARUS di-export dalam format C++ yang
// sangat compact. Gunakan script generate_model_atmega.py (lebih sederhana
// dari micromlgen untuk embedded device).
//
// Jika menggunakan micromlgen, pastikan dengan flag:
//   --max-depth=4 --n-estimators=10 (lebih kecil dari ESP32)

#include "inference_atmega.h"
#include <string.h>
#include <Arduino.h>

// Jika model RF di-export ke file terpisah
#if USE_ON_DEVICE_INFERENCE
  #include "model_rf_atmega.h"  // Model untuk ATmega (lebih ringan)
#endif

InferenceATmega::InferenceATmega() {
    reset();
}

void InferenceATmega::reset() {
    memset(adc_sum_, 0, sizeof(adc_sum_));
    memset(adc_max_, 0, sizeof(adc_max_));
    count_ = 0;
}

void InferenceATmega::accumulate(const uint16_t* adc) {
    if (!adc) return;
    
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        adc_sum_[i] += adc[i];
        if (adc[i] > adc_max_[i]) {
            adc_max_[i] = adc[i];
        }
    }
    count_++;
}

float InferenceATmega::computeMean(uint8_t sensor_idx) {
    if (count_ == 0) return 0.0f;
    if (sensor_idx >= NUM_SENSORS) return 0.0f;
    return (float)adc_sum_[sensor_idx] / (float)count_;
}

float InferenceATmega::computeMax(uint8_t sensor_idx) {
    if (sensor_idx >= NUM_SENSORS) return 0.0f;
    return (float)adc_max_[sensor_idx];
}

InferenceResult InferenceATmega::predict() {
    InferenceResult result;
    result.sample_count = count_;
    result.confidence = 0.0f;
    
#if USE_ON_DEVICE_INFERENCE
    if (count_ == 0) {
        result.class_id = -1;
        result.label = "N/A";
        return result;
    }
    
    // Bangun vektor fitur: 48 fitur.
    // 10 mean + 10 max + 10 sum (AUC) + 9 ratio to MQ135 + 9 ratio to TGS822
    float features[48];
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        features[i]                   = computeMean(i);
        features[i + NUM_SENSORS]    = computeMax(i);
        features[i + NUM_SENSORS * 2] = (float)adc_sum_[i]; // sum (AUC)
    }

    // Ratios to MQ135 (index 1)
    float mq135_max = computeMax(1);
    if (mq135_max <= 0.0f) mq135_max = 1.0f;
    uint8_t feat_idx = 30;
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        if (i != 1) {
            features[feat_idx++] = computeMax(i) / mq135_max;
        }
    }

    // Ratios to TGS822 (index 0)
    float tgs822_max = computeMax(0);
    if (tgs822_max <= 0.0f) tgs822_max = 1.0f;
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        if (i != 0) {
            features[feat_idx++] = computeMax(i) / tgs822_max;
        }
    }
    
    // Jalankan inference (implementasi tergantung format model_rf_atmega.h)
    // Untuk ATmega, bisa gunakan simple decision tree tanpa library eksternal
    // atau gunakan model yang di-port dari micromlgen
    result.class_id = doInference(features);
    result.label = (result.class_id >= 0 && result.class_id < NUM_CLASSES) 
                   ? CLASS_LABELS[result.class_id] 
                   : "N/A";
#else
    result.class_id = -1;
    result.label = "N/A";
#endif
    
    return result;
}

const char* InferenceATmega::predictLabel() {
    InferenceResult result = predict();
    return result.label;
}

void InferenceATmega::printResult() {
#if USE_ON_DEVICE_INFERENCE
    if (count_ == 0) {
        Serial.println(F("{\"event\":\"INFERENCE\",\"error\":\"no data\"}"));
        return;
    }
    
    InferenceResult result = predict();
    Serial.print(F("{\"event\":\"INFERENCE\",\"result\":\""));
    Serial.print(result.label);
    Serial.print(F("\",\"samples\":"));
    Serial.print(count_);
    Serial.println(F("}"));
#else
    Serial.println(F("{\"event\":\"INFERENCE\",\"result\":\"N/A\","
                     "\"note\":\"USE_ON_DEVICE_INFERENCE=0 or model not included\"}"));
#endif
}

// Placeholder untuk fungsi inference yang akan di-generate
// atau di-implement berdasarkan model yang dipilih
#if !defined(USE_ON_DEVICE_INFERENCE) || !USE_ON_DEVICE_INFERENCE
int doInference(float* features) {
    return -1;
}
#endif
