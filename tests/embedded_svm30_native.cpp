// Native parity test fixture only; NOT part of the ATmega production firmware.
// Input: one row per ADC sample: cycle phase(0 purge/1 collect) index ADC[10].
// Output: JSON with 30 extracted features, libsvm predicted class and margin.
#include "../src/embedded_svm30_features.h"
#include "../src/embedded_svm30_classifier.h"
#include <iomanip>
#include <iostream>
#include <stdint.h>

int main() {
  EmbeddedSvm30::Features extractor;
  for (unsigned n=0; n<900; ++n) {
    unsigned cycle=0,phase=0,index=0;
    unsigned adc[10] = {};
    if (!(std::cin >> cycle >> phase >> index)) {
      std::cerr << "MISSING_SAMPLE_AT_" << n << "\n";
      return 2;
    }
    uint16_t sensor[10] = {};
    for (unsigned i=0;i<10;++i) {
      if (!(std::cin >> adc[i]) || adc[i]>32767) {
        std::cerr << "INVALID_ADC_AT_" << n << "\n";
        return 2;
      }
      sensor[i]=static_cast<uint16_t>(adc[i]);
    }
    if (cycle>255 || phase>1 || index>255 ||
        !extractor.add(sensor,static_cast<uint8_t>(cycle),
                       static_cast<EmbeddedSvm30::Phase>(phase),
                       static_cast<uint8_t>(index))) {
      std::cerr << "SESSION_INVALID_AT_" << n << "\n";
      return 3;
    }
  }
  unsigned extra=0;
  if (std::cin >> extra) {
    std::cerr << "EXTRA_ROWS\n";
    return 4;
  }
  float raw[EmbeddedSvm30::kNumFeatures]={};
  if (!extractor.complete() || !extractor.copyFeatures(raw)) {
    std::cerr << "FEATURES_NOT_COMPLETE\n";
    return 5;
  }
  uint8_t margin=0;
  float pairScores[3]={};
  const EmbeddedSvm30::RoastClass cls =
      EmbeddedSvm30::Classifier::predict(raw,&margin,pairScores);
  if (cls==EmbeddedSvm30::INVALID) {
    std::cerr << "CLASSIFIER_INVALID\n";
    return 6;
  }
  std::cout << "{\"roast\":\""
            << EmbeddedSvm30::Classifier::label(cls)
            << "\",\"vote_margin\":" << static_cast<unsigned>(margin)
            << ",\"pair_scores\":[";
  std::cout << std::setprecision(10);
  for (unsigned i=0;i<3;++i) {
    if (i) std::cout << ',';
    std::cout << pairScores[i];
  }
  std::cout << "],\"features\":[";
  std::cout << std::setprecision(10);
  for (unsigned i=0;i<EmbeddedSvm30::kNumFeatures;++i) {
    if (i) std::cout << ',';
    std::cout << raw[i];
  }
  std::cout << "]}\n";
  return 0;
}
