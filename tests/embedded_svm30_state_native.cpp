// B2/B3 state-machine and error-path QA; no MCU or serial access.
#include "../src/embedded_svm30_features.h"
#include "../src/embedded_svm30_classifier.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

using namespace EmbeddedSvm30;

static void addFull(Features &s, const uint16_t *adc) {
  for (uint8_t cycle=1;cycle<=30;++cycle) {
    for (uint8_t i=1;i<=25;++i)
      assert(s.add(adc,cycle,PURGING,i));
    for (uint8_t i=1;i<=5;++i)
      assert(s.add(adc,cycle,COLLECTING,i));
  }
}

int main() {
  Features s;
  float f[kNumFeatures]={};
  uint16_t adc[10]={};
  for (uint8_t i=0;i<10;++i) adc[i]=static_cast<uint16_t>(14000+100*i);
  assert(!s.complete() && !s.copyFeatures(f));
  assert(!s.add(nullptr,1,PURGING,1));
  assert(s.bad() && !s.add(adc,1,PURGING,1));
  s.reset();
  assert(s.add(adc,1,PURGING,1));
  assert(!s.add(adc,1,COLLECTING,1));  // wrong phase
  assert(s.bad() && !s.copyFeatures(f));
  s.reset();
  assert(!s.add(adc,1,PURGING,2)); // missing first sample
  s.reset();
  uint16_t broken[10]={};
  for (uint8_t i=0;i<10;++i) broken[i]=adc[i];
  broken[kAdcMq8]=32768;
  assert(!s.add(broken,1,PURGING,1));
  s.reset();
  addFull(s,adc);
  assert(s.complete() && s.samples()==900 && s.copyFeatures(f));
  assert(!s.add(adc,31,PURGING,1)); // 901st sample is forbidden
  assert(s.bad() && !s.copyFeatures(f));
  s.reset();
  addFull(s,adc);
  assert(s.copyFeatures(f));
  assert(f[28]==0.0f); // global range from constant collecting
  assert(f[18]==0.0f && f[20]==0.0f && f[21]==0.0f && f[23]==0.0f);
  float corrupted[kNumFeatures]={};
  for (uint8_t i=0;i<kNumFeatures;++i) corrupted[i]=f[i];
  corrupted[2]=NAN;
  assert(Classifier::predict(corrupted)==INVALID);
  corrupted[2]=INFINITY;
  assert(Classifier::predict(corrupted)==INVALID);
  corrupted[2]=1.0e30f;
  assert(Classifier::predict(corrupted)==INVALID);
  assert(Classifier::predict(nullptr)==INVALID);
  assert(Classifier::predict(f)!=INVALID);
  assert(Classifier::label(INVALID)[0]=='N');
  printf("EMBEDDED_SVM30_STATE_AND_FAIL_CLOSED_NATIVE_PASS\n");
  return 0;
}
