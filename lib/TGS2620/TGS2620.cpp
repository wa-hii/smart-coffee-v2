#include "TGS2620.h"

double TGS2620::calibrate(double ratio_clean_air){
  double RS_air; //Define variable for sensor resistance
  double R0; //Define variable for R0
  RS_air = ((_VOLT_RESOLUTION * RL) / VRL )-RL; //Calculate RS in fresh air
  if(RS_air < 0)  RS_air = 0; //No negative values accepted.
  R0 = RS_air / ratio_clean_air; //Calculate R0 
  if(R0 < 0)  R0 = 0; //No negative values accepted.
  return R0;
}
void TGS2620::setADC(int value)
{
  this-> VRL = (value) * _VOLT_RESOLUTION / ((pow(2, _ADC_Bit_Resolution)) - 1); 
  this-> _adc =  value;
}
void TGS2620::calculateRatio(double adc){
  VRL = adc * (_VOLT_RESOLUTION/_ADC_MAX_VALUE); 
  // Serial.print("vrl : ");
  // Serial.println(VRL);
  Rs = ((_VOLT_RESOLUTION/VRL) - ratio_in_air)*(RL); 
  // Serial.print("Rs : ");
  // Serial.println(Rs);
  ratio = Rs/Ro;
}

double TGS2620::calculatePpm(int adc, double a, double b){
  // calculateRatio(adc);
  float _RS_Calc = ((_VOLT_RESOLUTION*RL)/VRL)-RL; //Get value of RS in a gas
  if(_RS_Calc < 0)  _RS_Calc = 0; //No negative values accepted.
  double _ratio = _RS_Calc / Ro;   // Get ratio RS_gas/RS_air
  if(_ratio <= 0)  _ratio = 0; //No negative values accepted or upper datasheet recomendation.

  // float ratio = getRatio();
  double ppm = a * pow(_ratio, b);
  if(ppm < 0) ppm = 0;

  // Serial.print("Ro : ");
  // Serial.println(Ro);
  // Serial.print("ratio : ");
  // Serial.println(ratio);
  // Serial.print("b : ");
  // Serial.println(b);
  // Serial.print("m : ");
  // Serial.println(m);
  // Serial.print("ppm : ");
  // Serial.println(ppm);

  return ppm;
}