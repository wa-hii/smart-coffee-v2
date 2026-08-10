// ═════════════════════════════════════════════════════════════════════════════
// TGSSensor.h — Library TGS Generik
// Untuk semua sensor TGS: TGS822, TGS2620, TGS2611, TGS2600, TGS2602,
// TGS813, TGS816, dll.
// Formula: Rs = (Vcc × RL / VRL) − RL, ratio = Rs/R0, ppm = a × ratio^b
// ═════════════════════════════════════════════════════════════════════════════
#pragma once
#include <Arduino.h>
#include <math.h>

class TGSSensor {
public:
    void  setR0(float r0)       { r0_ = r0; }
    void  setRL(float rl)       { rl_ = rl; }
    void  setRatioAir(float r)  { ratioAir_ = r; }
    void  setADC(int value);
    float calibrate(float ratioCleanAir);
    float calculatePpm(int adc, float a, float b);
    float getRatio() { return ratio_; }

private:
    float vcc_      = 6.144f;     // ADS1115 ±6.144 V
    float adcMax_   = 65536.0f;   // 16-bit ADC
    int   adcBits_  = 16;
    float vrl_      = 0.0f;
    float rl_       = 0.0f;
    float r0_       = 0.0f;
    float ratioAir_ = 0.0f;
    float ratio_    = 0.0f;
};
