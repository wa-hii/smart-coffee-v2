#include <Arduino.h>
#include <stdint.h>
#include <cmath>

class TGS2620 { // TODO : minimal tulisan gak gede kecil
  private:
    double _VOLT_RESOLUTION = 6.144;
    double _ADC_MAX_VALUE = 65536.0;
    int _ADC_Bit_Resolution = 16;
    double VRL = 0.0;
    double _adc = 0.0;
    double Rs = 0.0;
    double RL = 0.0;
    double Ro = 0.0;
    double ratio_in_air = 0.0;

    double ratio = 0.0;

  public:
    void setR0(double Ro_) {Ro = Ro_;}
    void setRL(double RL_) {RL = RL_;}
    void setRatioAir(double rat_) {ratio_in_air = rat_;}
    void setADC(int);
    double calibrate(double);
    void calculateRatio(double);
    double calculatePpm(int adc, double a, double b);

    double getRatio(){return ratio;}
};