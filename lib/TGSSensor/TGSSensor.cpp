// ═════════════════════════════════════════════════════════════════════════════
// TGSSensor.cpp — Implementasi Library TGS Generik
// ═════════════════════════════════════════════════════════════════════════════
#include "TGSSensor.h"

void TGSSensor::setADC(int value) {
    vrl_ = (float)value * vcc_ / (pow(2, adcBits_) - 1);
}

float TGSSensor::calibrate(float ratioCleanAir) {
    float rsAir = (vcc_ * rl_ / vrl_) - rl_;
    if (rsAir < 0) rsAir = 0;
    float r0 = rsAir / ratioCleanAir;
    if (r0 < 0) r0 = 0;
    return r0;
}

float TGSSensor::calculatePpm(int adc, float a, float b) {
    // VRL sudah di-set oleh setADC() sebelumnya
    float rsCalc = (vcc_ * rl_ / vrl_) - rl_;
    if (rsCalc < 0) rsCalc = 0;
    float ratio = (r0_ > 0) ? (rsCalc / r0_) : 0;
    if (ratio <= 0) ratio = 0;
    float ppm = a * pow(ratio, b);
    if (ppm < 0) ppm = 0;
    return ppm;
}
