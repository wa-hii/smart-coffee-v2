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
                        uint8_t votes[3] = { 0 };
                        // tree #1
                        if (x[5] <= 23397.0) {
                            votes[1] += 1;
                        }

                        else {
                            votes[0] += 1;
                        }

                        // tree #2
                        if (x[7] <= 24024.0) {
                            votes[0] += 1;
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #3
                        if (x[4] <= 14714.5) {
                            if (x[5] <= 23464.0) {
                                votes[2] += 1;
                            }

                            else {
                                votes[0] += 1;
                            }
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #4
                        if (x[5] <= 23395.5) {
                            votes[1] += 1;
                        }

                        else {
                            if (x[4] <= 13770.5) {
                                votes[2] += 1;
                            }

                            else {
                                votes[0] += 1;
                            }
                        }

                        // tree #5
                        if (x[7] <= 24024.0) {
                            votes[0] += 1;
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #6
                        if (x[7] <= 24024.0) {
                            votes[0] += 1;
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #7
                        if (x[0] <= 22440.0) {
                            votes[1] += 1;
                        }

                        else {
                            if (x[5] <= 23381.5) {
                                votes[1] += 1;
                            }

                            else {
                                votes[0] += 1;
                            }
                        }

                        // tree #8
                        if (x[0] <= 22493.5) {
                            if (x[3] <= 18773.0) {
                                votes[2] += 1;
                            }

                            else {
                                votes[0] += 1;
                            }
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #9
                        if (x[4] <= 14436.5) {
                            if (x[1] <= 3031.0) {
                                votes[0] += 1;
                            }

                            else {
                                votes[2] += 1;
                            }
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #10
                        if (x[5] <= 23395.5) {
                            votes[1] += 1;
                        }

                        else {
                            votes[2] += 1;
                        }

                        // tree #11
                        if (x[1] <= 2968.5) {
                            votes[0] += 1;
                        }

                        else {
                            if (x[3] <= 18935.5) {
                                if (x[1] <= 3031.0) {
                                    votes[0] += 1;
                                }

                                else {
                                    votes[2] += 1;
                                }
                            }

                            else {
                                votes[1] += 1;
                            }
                        }

                        // tree #12
                        if (x[5] <= 23395.5) {
                            votes[1] += 1;
                        }

                        else {
                            if (x[2] <= 20367.5) {
                                votes[2] += 1;
                            }

                            else {
                                votes[0] += 1;
                            }
                        }

                        // tree #13
                        if (x[1] <= 3039.5) {
                            if (x[5] <= 23405.5) {
                                if (x[6] <= 22987.0) {
                                    votes[2] += 1;
                                }

                                else {
                                    votes[1] += 1;
                                }
                            }

                            else {
                                votes[0] += 1;
                            }
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #14
                        if (x[0] <= 22324.5) {
                            votes[2] += 1;
                        }

                        else {
                            votes[1] += 1;
                        }

                        // tree #15
                        if (x[3] <= 18773.0) {
                            votes[2] += 1;
                        }

                        else {
                            if (x[5] <= 23381.5) {
                                votes[1] += 1;
                            }

                            else {
                                votes[0] += 1;
                            }
                        }

                        // return argmax of votes
                        uint8_t classIdx = 0;
                        float maxVotes = votes[0];

                        for (uint8_t i = 1; i < 3; i++) {
                            if (votes[i] > maxVotes) {
                                classIdx = i;
                                maxVotes = votes[i];
                            }
                        }

                        return classIdx;
                    }

                protected:
                };
            }
        }
    }