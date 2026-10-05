#include "TGS822.h"

float TGS822::calibrate(float ratio_clean_air){
  float RS_air; //Define variable for sensor resistance
  float R0; //Define variable for R0
  RS_air = ((_VOLT_RESOLUTION * RL) / VRL )-RL; //Calculate RS in fresh air
  if(RS_air < 0)  RS_air = 0; //No negative values accepted.
  R0 = RS_air / ratio_clean_air; //Calculate R0 
  if(R0 < 0)  R0 = 0; //No negative values accepted.
  return R0;
}
void TGS822::setADC(int value)
{
  this-> VRL = (value) * _VOLT_RESOLUTION / ((pow(2, _ADC_Bit_Resolution)) - 1); 
  this-> _adc =  value;
}
void TGS822::calculateRatio(float adc){
  float ratio_in_air = 1; //ppm , kyknya, gatau gak paham jg
  VRL = adc * (_VOLT_RESOLUTION/_ADC_MAX_VALUE); 
  Rs = ((_VOLT_RESOLUTION/VRL) - ratio_in_air)*(RL); 
  ratio = Rs/Ro;
}

float TGS822::calculatePpm(int adc, float a, float b){
  // calculateRatio(adc);
  float _RS_Calc = ((_VOLT_RESOLUTION*RL)/VRL)-RL; //Get value of RS in a gas
  if(_RS_Calc < 0)  _RS_Calc = 0; //No negative values accepted.
  double _ratio = _RS_Calc / Ro;   // Get ratio RS_gas/RS_air
  if(_ratio <= 0)  _ratio = 0; //No negative values accepted or upper datasheet recomendation.

  // float ratio = getRatio();
  float ppm = a * pow(_ratio, b);

  return ppm;
}