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
                        uint8_t votes[2] = { 0 };
                        // tree #1
                        if (x[15] <= 5915.0) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #2
                        if (x[8] <= 2981.0) {
                            votes[0] += 1;
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #3
                        if (x[15] <= 6035.5) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #4
                        if (x[8] <= 2981.0) {
                            votes[0] += 1;
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #5
                        if (x[15] <= 5915.0) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #6
                        if (x[15] <= 5993.0) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #7
                        if (x[0] <= 2976.9638671875) {
                            votes[0] += 1;
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #8
                        if (x[8] <= 2981.0) {
                            votes[0] += 1;
                        }

                        else {
                            if (x[7] <= 7008.416809082031) {
                                votes[1] += 1;
                            }

                            else {
                                votes[0] += 1;
                            }
                        }

                        // tree #9
                        if (x[7] <= 5987.177551269531) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #10
                        if (x[14] <= 7641.0) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #11
                        if (x[6] <= 7073.202087402344) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #12
                        if (x[6] <= 7073.202087402344) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #13
                        if (x[15] <= 6035.5) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #14
                        if (x[6] <= 6841.577575683594) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #15
                        if (x[0] <= 2974.2694091796875) {
                            votes[0] += 1;
                        }

                        else {
                            votes[1] += 1;
                        }

                        // return argmax of votes
                        uint8_t classIdx = 0;
                        float maxVotes = votes[0];

                        for (uint8_t i = 1; i < 2; i++) {
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