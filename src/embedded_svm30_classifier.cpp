#include "embedded_svm30_classifier.h"

#if defined(ENABLE_AVR_SVM30) && ENABLE_AVR_SVM30

#include "../private/embedded_svm30_model.h"  // private, SHA-pinned, NOT Git
#include <math.h>

namespace EmbeddedSvm30 {
namespace {
namespace M = EmbeddedSvm30Parameters;

#ifdef __AVR__
// Explicit flash reads: no 16KB support vector table in ATmega SRAM.
static float flashFloat(const float *p) { return pgm_read_float(p); }
static uint8_t flashByte(const uint8_t *p) { return pgm_read_byte(p); }
#else
static float flashFloat(const float *p) { return *p; }
static uint8_t flashByte(const uint8_t *p) { return *p; }
#endif

}  // namespace

RoastClass Classifier::predict(const float raw[kNumFeatures],
                               uint8_t *minVoteMargin, float pairScores[3]) {
  if (!raw || M::kFeatures != kNumFeatures || M::kSV != 125 ||
      flashByte(&M::kNSupport[0]) != 44 ||
      flashByte(&M::kNSupport[1]) != 34 ||
      flashByte(&M::kNSupport[2]) != 47) return INVALID;

  float scaled[kNumFeatures];
  for (uint8_t i = 0; i < kNumFeatures; ++i) {
    if (!isfinite(raw[i])) return INVALID;
    const float scale = flashFloat(&M::kScale[i]);
    const float mean = flashFloat(&M::kMean[i]);
    if (!isfinite(scale) || scale <= 0.0f || !isfinite(mean)) return INVALID;
    scaled[i] = (raw[i] - mean) / scale;
    if (!isfinite(scaled[i]) || fabsf(scaled[i]) > 1000000.0f) return INVALID;
  }

  // Precompute one RBF value per support vector (125 kernel evaluations).
  // 125 x 4 = 500 bytes stack, NOT a 15KB SRAM copy of support vectors.
  float kernel[125];
  for (uint8_t sv = 0; sv < M::kSV; ++sv) {
    float squared = 0.0f;
    const uint16_t base = static_cast<uint16_t>(sv) * kNumFeatures;
    for (uint8_t f = 0; f < kNumFeatures; ++f) {
      const float d = scaled[f] - flashFloat(&M::kSVectors[base + f]);
      squared += d * d;
    }
    if (!isfinite(squared)) return INVALID;
    kernel[sv] = expf(-M::kGamma * squared);
    if (!isfinite(kernel[sv])) return INVALID;
  }

  // Equivalent to libsvm's multiclass svm_predict_values:
  // for every class pair (i,j), coef1 = dual_coef_[j-1][i's SV],
  // coef2 = dual_coef_[i][j's SV], and one positive vote for i when
  // pairwise decision > 0. For this scikit-learn 1.7.2 SVC bundle,
  // the exported intercept_ is ALREADY in libsvm orientation: ADD it.
  uint8_t votes[3] = {0, 0, 0};
  uint8_t start[3] = {0, 0, 0};
  for (uint8_t i = 1; i < 3; ++i)
    start[i] = static_cast<uint8_t>(
        start[i-1] + flashByte(&M::kNSupport[i-1]));
  uint8_t pair = 0;
  for (uint8_t i = 0; i < 3; ++i) {
    for (uint8_t j = i+1; j < 3; ++j) {
      float score = 0.0f;
      const uint8_t ni = flashByte(&M::kNSupport[i]);
      const uint8_t nj = flashByte(&M::kNSupport[j]);
      const uint16_t coefRowI = static_cast<uint16_t>(j-1) * M::kSV;
      const uint16_t coefRowJ = static_cast<uint16_t>(i) * M::kSV;
      for (uint8_t k = 0; k < ni; ++k) {
        const uint8_t sv = static_cast<uint8_t>(start[i] + k);
        score += flashFloat(&M::kDualCoef[coefRowI+sv]) * kernel[sv];
      }
      for (uint8_t k = 0; k < nj; ++k) {
        const uint8_t sv = static_cast<uint8_t>(start[j] + k);
        score += flashFloat(&M::kDualCoef[coefRowJ+sv]) * kernel[sv];
      }
      score += flashFloat(&M::kIntercept[pair]);
      if (!isfinite(score)) return INVALID;
      if (pairScores) pairScores[pair] = score;
      ++votes[score > 0.0f ? i : j];
      ++pair;
    }
  }

  // libsvm's deterministic tie rule is smallest class index.
  uint8_t winner = 0;
  for (uint8_t i = 1; i < 3; ++i)
    if (votes[i] > votes[winner]) winner = i;
  const uint8_t other = votes[(winner+1)%3] > votes[(winner+2)%3]
                            ? votes[(winner+1)%3] : votes[(winner+2)%3];
  if (minVoteMargin) *minVoteMargin = votes[winner] - other;
  return static_cast<RoastClass>(winner);
}

const char *Classifier::label(RoastClass cls) {
  switch (cls) {
    case DARK: return "dark";
    case LIGHT: return "light";
    case MEDIUM: return "medium";
    default: return "N/A";
  }
}

}  // namespace EmbeddedSvm30

#endif  // ENABLE_AVR_SVM30
