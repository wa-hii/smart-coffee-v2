// Compile-only proof that the standalone SVM30 classes link on ATmega2560.
// NEVER UPLOAD this firmware. It contains no sensor/valve/Nextion controls.
#include <Arduino.h>
#include "../src/embedded_svm30_features.h"
#include "../src/embedded_svm30_classifier.h"

static EmbeddedSvm30::Features featureState;
static volatile int8_t lastClass = -1;

void setup() {
  uint16_t sensor[10] = {};
  // A deterministic 900-row synthetic fixture forces linking of all code.
  for (uint8_t cycle = 1; cycle <= 30; ++cycle) {
    for (uint8_t idx = 1; idx <= 25; ++idx)
      if (!featureState.add(sensor, cycle, EmbeddedSvm30::PURGING, idx))
        return;
    for (uint8_t idx = 1; idx <= 5; ++idx)
      if (!featureState.add(sensor, cycle, EmbeddedSvm30::COLLECTING, idx))
        return;
  }
  float raw[EmbeddedSvm30::kNumFeatures] = {};
  if (featureState.copyFeatures(raw))
    lastClass = static_cast<int8_t>(
        EmbeddedSvm30::Classifier::predict(raw));
}

void loop() {}
