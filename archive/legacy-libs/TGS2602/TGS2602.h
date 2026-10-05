#include "SensorBase.h"
#include <Arduino.h>

#define F2602 A2

class TGS2602 {
  private:
    float VRL_F2602;
    float Rs_F2602;
    float RL_F2602 = 0.45;
    float Ro_F2602 = 59;
    float ratio_F2602;
    float NH3_A = 0.92372844;
    float NH3_B = -0.291578925;
    float H2S_A = 0.38881036;
    float H2S_B = -0.35010059;
    float VOC_A = 0.3220722;
    float VOC_B = -0.6007520;

    float ppm_NH3;
    float ppm_H2S;
    float ppm_VOC;
  public:
    void calculateRatio(float);
    void calculateppm_NH3(float);
    void calculateppm_H2S(float);
    void calculateppm_VOC(float);

    float getRatio(){return ratio_F2602;}
    float getppm_NH3(){return ppm_NH3;}
    float getppm_H2S(){return ppm_H2S;}
    float getppm_VOC(){return ppm_VOC;}
};