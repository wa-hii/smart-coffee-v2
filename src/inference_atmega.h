// inference_atmega.h — Optimized Inference untuk ATmega (Arduino Mega 2560)
// 
// Karakteristik ATmega2560:
//   - RAM: 8 KB (sangat terbatas!)
//   - Clock: 16 MHz
//   - Storage: 256 KB Flash (cukup untuk model + code)
//
// Strategi optimasi:
//   1. Gunakan uint16_t bukan double (hemat 8 byte per nilai)
//   2. Dapatkan mean/max on-the-fly saat predict, jangan simpan array besar
//   3. Model RF di-export ke C header dengan ukuran minimal
//
// Cara pakai:
//   #include "inference_atmega.h"
//   InferenceATmega inference;
//   inference.reset();
//   for(int i=0; i<cycles; i++) {
//       uint16_t adc_vals[NUM_SENSORS] = { ... };
//       inference.accumulate(adc_vals);
//   }
//   InferenceResult result = inference.predict();
//   Serial.println(result.label);  // "light", "medium", "dark"

#pragma once
#include "inference_common.h"

class InferenceATmega : public InferenceBase {
public:
    InferenceATmega();
    ~InferenceATmega() {}
    
    void reset() override;
    void accumulate(const uint16_t* adc) override;
    InferenceResult predict() override;
    const char* predictLabel() override;
    void printResult() override;
    
private:
    // Gunakan fixed-point arithmetic untuk menghemat RAM
    // sum_ dan max_ di-compute on-the-fly saat predict()
    // hanya menyimpan counter dan akumulasi untuk mean calculation
    uint32_t adc_sum_[NUM_SENSORS];  // akumulasi nilai ADC untuk mean
    uint16_t adc_max_[NUM_SENSORS];  // nilai max dari setiap sensor
    
    // Helper untuk compute features dan jalankan inference tree
    float computeMean(uint8_t sensor_idx);
    float computeMax(uint8_t sensor_idx);
};
