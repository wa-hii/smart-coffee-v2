#pragma once

#include <Arduino.h>
#include <Wire.h>

class Sht30 {
public:
  explicit Sht30(TwoWire &wire = Wire, uint8_t address = 0x44)
      : wire_(wire), address_(address) {}

  bool begin();
  bool read(float &temperatureC, float &humidityRh);

private:
  static uint8_t crc8(const uint8_t *data, uint8_t length);

  TwoWire &wire_;
  uint8_t address_;
};
