// B3: libsvm-compatible one-vs-one SVC RBF inference for 30-dimensional input.
// No heap, Serial, sensor I/O, Raspberry Pi, persistence, or actuator control.
#pragma once
#include <stdint.h>
#include "embedded_svm30_features.h"

namespace EmbeddedSvm30 {

// The class order is exact from final_svm.joblib: dark, light, medium.
enum RoastClass : int8_t { INVALID=-1, DARK=0, LIGHT=1, MEDIUM=2 };

class Classifier {
 public:
  // Input is raw ADC-derived 30 feature vector, not already standardized.
  // Uses pinned StandardScaler and all 125 support vectors from PROGMEM.
  // Returns INVALID on NaN, Inf, badly scaled values or invalid model.
  // optional minVoteMargin: top-vs-runner-up vote difference (0 = tie).
  // optional pairScores: decision scores for dark/light, dark/medium,
  // light/medium (libsvm ovo order), for golden parity diagnostics only.
  static RoastClass predict(const float raw[kNumFeatures],
                            uint8_t *minVoteMargin = nullptr,
                            float pairScores[3] = nullptr);
  static const char *label(RoastClass cls);
};

}  // namespace EmbeddedSvm30
