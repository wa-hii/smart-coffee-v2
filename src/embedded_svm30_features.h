// B2: streaming features for the SHA-pinned 30-feature roast SVM.
// Pure C++11: no Arduino, heap allocation, CSV buffer or Raspberry Pi.
// User-supplied model expects ABSOLUTE ADC, not baseline subtraction.
#pragma once
#include <stdint.h>

namespace EmbeddedSvm30 {

static constexpr uint8_t kNumFeatures = 30;
static constexpr uint8_t kCycles = 30;
static constexpr uint16_t kSamples = 900;

// Indexes in the existing 10-channel SensorArray ADC order.
static constexpr uint8_t kAdcTgs822 = 0;
static constexpr uint8_t kAdcTgs2602 = 6;
static constexpr uint8_t kAdcMq8 = 7;
static constexpr uint8_t kAdcTgs816 = 9;
enum Phase : uint8_t { PURGING = 0, COLLECTING = 1 };

// Welford statistics: stable running population variance, O(1) storage.
struct RunningStat {
  float mean;
  float m2;
  uint8_t n;
  void clear();
  void add(float x);
  float stdPopulation() const;
};

class Features {
 public:
  Features() { reset(); }
  void reset();

  // Strict 1-based cycle/phase sample indices: purge 1..25, collect 1..5.
  // Returns false and permanently faults this session on any invalid input.
  bool add(const uint16_t *adc10, uint8_t cycle, Phase phase, uint8_t index);
  bool complete() const { return !bad_ && total_ == kSamples && cycle_ == 31; }
  bool bad() const { return bad_; }
  uint16_t samples() const { return total_; }
  bool copyFeatures(float out[kNumFeatures]) const;

 private:
  struct SensorCycle {
    RunningStat purge;
    RunningStat collect;
    uint16_t purgeMin;
    uint16_t collectMin;
    uint16_t collectMax;
    uint16_t collectFirst;
    float purgeSlopeSum;
    float collectSlopeSum;
    void reset();
  };
  RunningStat featureStats_[kNumFeatures];
  SensorCycle sensor_[4];  // TGS822, TGS2602, TGS816, MQ8
  uint16_t global816Min_;
  uint16_t global816Max_;
  uint16_t total_;
  uint8_t cycle_;
  uint8_t index_;
  Phase phase_;
  bool bad_;

  void push(uint8_t feature, float value);
  void finishPurge();
  void finishCollect();
};

}  // namespace EmbeddedSvm30
