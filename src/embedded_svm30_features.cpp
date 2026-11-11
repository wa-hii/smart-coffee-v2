#include "embedded_svm30_features.h"

#if defined(ENABLE_AVR_SVM30) && ENABLE_AVR_SVM30

#include <math.h>
#include <string.h>

namespace EmbeddedSvm30 {

void RunningStat::clear() {
  mean = 0.0f;
  m2 = 0.0f;
  n = 0;
}

void RunningStat::add(float value) {
  ++n;
  const float d = value - mean;
  mean += d / static_cast<float>(n);
  const float d2 = value - mean;
  m2 += d * d2;
}

float RunningStat::stdPopulation() const {
  if (!n) return NAN;
  const float variance = m2 / static_cast<float>(n);
  return sqrtf(variance > 0.0f ? variance : 0.0f);
}

void Features::SensorCycle::reset() {
  purge.clear();
  collect.clear();
  purgeMin = 32767;
  collectMin = 32767;
  collectMax = 0;
  collectFirst = 0;
  purgeSlopeSum = 0.0f;
  collectSlopeSum = 0.0f;
}

void Features::reset() {
  for (uint8_t i = 0; i < kNumFeatures; ++i) featureStats_[i].clear();
  for (uint8_t j = 0; j < 4; ++j) sensor_[j].reset();
  global816Min_ = 32767;
  global816Max_ = 0;
  total_ = 0;
  cycle_ = 1;
  index_ = 1;
  phase_ = PURGING;
  bad_ = false;
}

void Features::push(uint8_t idx, float value) {
  if (!isfinite(value)) {
    bad_ = true;
    return;
  }
  featureStats_[idx].add(value);
}

void Features::finishPurge() {
  // Least-squares slope over x=0..24. sum((x-12)^2) = 1300.
  push(1, sensor_[0].purge.mean);
  push(5, static_cast<float>(sensor_[0].purgeMin));
  push(9, sensor_[2].purge.stdPopulation());
  push(10, sensor_[1].purgeSlopeSum / 1300.0f);
  push(12, sensor_[2].purgeSlopeSum / 1300.0f);
  const float std2602 = sensor_[1].purge.stdPopulation();
  push(16, std2602);
  push(18, std2602);  // same statistic aggregated as population std across cycles
  push(21, sensor_[2].purge.stdPopulation());
  push(25, sensor_[3].purge.mean);
}

void Features::finishCollect() {
  // All collecting cycles contain exactly five points. Their first/last
  // 5-point means, plateau and mean are therefore the same feature value.
  const float m822 = sensor_[0].collect.mean;
  const float m8 = sensor_[3].collect.mean;
  push(0, static_cast<float>(sensor_[0].collectMax));
  push(2, m822);
  push(3, m822);
  push(4, m822);
  push(6, m822);
  push(7, 5.0f * m822);  // AUC in original helper is sum(samples), NOT trapezoid
  push(8, (static_cast<float>(sensor_[1].collectMax) -
            static_cast<float>(sensor_[1].collectFirst)) /
           (fabsf(static_cast<float>(sensor_[1].collectFirst)) + 1e-6f));
  push(11, sensor_[2].collect.stdPopulation());
  const float delta816 = static_cast<float>(
      sensor_[2].collectMax - sensor_[2].collectMin);
  push(13, delta816);
  push(20, delta816);
  const float delta2602 = static_cast<float>(
      sensor_[1].collectMax - sensor_[1].collectMin);
  push(14, delta2602);
  push(23, delta2602);
  // slope x=0..4: sum((x-2)^2) = 10.
  push(15, sensor_[1].collectSlopeSum / 10.0f);
  push(17, static_cast<float>(sensor_[3].collectMax));
  push(19, sensor_[1].collect.stdPopulation());
  push(22, 5.0f * m8);
  push(24, m8);
  push(26, m8);
  push(27, sensor_[3].collect.stdPopulation());
  push(29, sensor_[0].collectSlopeSum / 10.0f);
}

bool Features::add(const uint16_t *adc10, uint8_t cycle, Phase phase,
                   uint8_t index) {
  if (bad_ || !adc10 || total_ >= kSamples || cycle != cycle_ ||
      phase != phase_ || index != index_) {
    bad_ = true;
    return false;
  }
  static const uint8_t kChannel[4] = {
      kAdcTgs822, kAdcTgs2602, kAdcTgs816, kAdcMq8};
  for (uint8_t k = 0; k < 4; ++k) {
    const uint16_t adc = adc10[kChannel[k]];
    if (adc > 32767U) {
      bad_ = true;
      return false;
    }
    SensorCycle &s = sensor_[k];
    if (phase == PURGING) {
      s.purge.add(static_cast<float>(adc));
      if (adc < s.purgeMin) s.purgeMin = adc;
      s.purgeSlopeSum +=
          static_cast<float>(static_cast<int16_t>(index) - 13) *
          static_cast<float>(adc);
    } else {
      s.collect.add(static_cast<float>(adc));
      if (index == 1) s.collectFirst = adc;
      if (adc < s.collectMin) s.collectMin = adc;
      if (adc > s.collectMax) s.collectMax = adc;
      s.collectSlopeSum +=
          static_cast<float>(static_cast<int16_t>(index) - 3) *
          static_cast<float>(adc);
      if (k == 2) {
        if (adc < global816Min_) global816Min_ = adc;
        if (adc > global816Max_) global816Max_ = adc;
      }
    }
  }
  ++total_;
  if (phase == PURGING && index == 25) {
    finishPurge();
    phase_ = COLLECTING;
    index_ = 1;
  } else if (phase == COLLECTING && index == 5) {
    finishCollect();
    ++cycle_;
    if (cycle_ <= kCycles) {
      for (uint8_t k = 0; k < 4; ++k) sensor_[k].reset();
    }
    phase_ = PURGING;
    index_ = 1;
  } else {
    ++index_;
  }
  return !bad_;
}

bool Features::copyFeatures(float out[kNumFeatures]) const {
  if (!out || !complete()) return false;
  for (uint8_t i = 0; i < kNumFeatures; ++i) {
    if (i == 28) {
      out[i] = static_cast<float>(global816Max_ - global816Min_);
    } else {
      if (featureStats_[i].n != 30) return false;
      // The original helper's *_std is population std of 30 cycle metrics.
      switch (i) {
      case 18: case 20: case 21: case 23: case 29:
        out[i] = featureStats_[i].stdPopulation();
        break;
      default:
        out[i] = featureStats_[i].mean;
        break;
      }
    }
    if (!isfinite(out[i])) return false;
  }
  return true;
}

}  // namespace EmbeddedSvm30

#endif  // ENABLE_AVR_SVM30
