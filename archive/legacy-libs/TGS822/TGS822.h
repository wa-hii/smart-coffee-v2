#include <Arduino.h>

class TGS822 { // TODO : minimal tulisan gak gede kecil
  private:
    float _VOLT_RESOLUTION = 6.144;
    float _ADC_MAX_VALUE = 65536.0;
    int _ADC_Bit_Resolution = 16;
    float VRL = 0.0;
    float _adc = 0.0;
    float Rs = 0.0;
    float RL = 0.0;
    float Ro = 0.0;

    float ratio = 0.0;

  public:
    void setR0(float Ro_) {Ro = Ro_;}
    void setRL(float RL_) {RL = RL_;}
    void setADC(int);
    float calibrate(float);
    void calculateRatio(float);
    float calculatePpm(int adc, float a, float b);

    float getRatio(){return ratio;}
};