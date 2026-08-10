// inference.h — Modul Inferensi AI On-Device (TinyML)
// Akumulasi fitur (mean + max ADC) dan klasifikasi Random Forest
#pragma once
#include "sensor.h" // NUM_SENSORS
#include <Arduino.h>

// Aktifkan inferensi on-device SETELAH model_rf.h di-generate
// oleh script 4_train_rf.py, lalu flash ulang.
// Bisa di-override via build_flags: -DUSE_ON_DEVICE_INFERENCE=1
#ifndef USE_ON_DEVICE_INFERENCE
#define USE_ON_DEVICE_INFERENCE 0
#endif

class Inference {
public:
  void reset(); // Reset akumulasi fitur
  void
  accumulate(const uint16_t *adcValues); // Tambah sampel ke running sum + max
  uint32_t getFeatureCount() const { return count_; }

  int predict();              // Return class index (0–2), atau -1 jika error
  const char *predictLabel(); // Return "light" / "medium" / "dark" / "N/A"
  void printResult();         // Kirim JSON hasil inferensi via Serial

private:
  double sum_[NUM_SENSORS] = {};
  uint16_t max_[NUM_SENSORS] = {};
  uint32_t count_ = 0;
};
