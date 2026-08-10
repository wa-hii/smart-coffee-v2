/*
 * model_rf.h — Random Forest untuk E-NOSE Kopi
 * Di-generate otomatis oleh 4_train_rf.py via micromlgen
 *
 * Label   : light(0) / medium(1) / dark(2)
 * Fitur   : 16 (mean_adc_mq135, mean_adc_mq136, mean_adc_mq137, mean_adc_mq138...)
 * Trees   : 15
 * MaxDepth: 6
 *
 * Cara pakai di main.cpp:
 *   #define USE_ON_DEVICE_INFERENCE 1
 *   #include "model_rf.h"
 *   Eloquent::ML::Port::RandomForest classifier;
 *   float features[16] = { mean_mq135, ..., max_tgs2620 };
 *   const char* label = classifier.predictLabel(features);
 */
#pragma once
#include <cstdarg>
namespace Eloquent {
    namespace ML {
        namespace Port {
            class RandomForest {
                public:
                    /**
                    * Predict class for features vector
                    */
                    int predict(float *x) {
                        uint8_t votes[1] = { 0 };
                        // tree #1
                        votes[0] += 1;
                        // tree #2
                        votes[0] += 1;
                        // tree #3
                        votes[0] += 1;
                        // tree #4
                        votes[0] += 1;
                        // tree #5
                        votes[0] += 1;
                        // tree #6
                        votes[0] += 1;
                        // tree #7
                        votes[0] += 1;
                        // tree #8
                        votes[0] += 1;
                        // tree #9
                        votes[0] += 1;
                        // tree #10
                        votes[0] += 1;
                        // tree #11
                        votes[0] += 1;
                        // tree #12
                        votes[0] += 1;
                        // tree #13
                        votes[0] += 1;
                        // tree #14
                        votes[0] += 1;
                        // tree #15
                        votes[0] += 1;
                        // return argmax of votes
                        uint8_t classIdx = 0;
                        float maxVotes = votes[0];

                        for (uint8_t i = 1; i < 1; i++) {
                            if (votes[i] > maxVotes) {
                                classIdx = i;
                                maxVotes = votes[i];
                            }
                        }

                        return classIdx;
                    }

                    /**
                    * Predict readable class name
                    */
                    const char* predictLabel(float *x) {
                        return idxToLabel(predict(x));
                    }

                    /**
                    * Convert class idx to readable name
                    */
                    const char* idxToLabel(uint8_t classIdx) {
                        switch (classIdx) {
                            case light:
                            return "0";
                            case medium:
                            return "1";
                            case dark:
                            return "2";
                            default:
                            return "Houston we have a problem";
                        }
                    }

                protected:
                };
            }
        }
    }