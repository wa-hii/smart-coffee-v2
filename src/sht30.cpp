#include "sht30.h"

bool Sht30::begin() {
  wire_.beginTransmission(address_);
  return wire_.endTransmission() == 0;
}

bool Sht30::read(float &temperatureC, float &humidityRh) {
  // Single-shot, high-repeatability measurement without clock stretching.
  wire_.beginTransmission(address_);
  wire_.write(0x24);
  wire_.write(0x00);
  if (wire_.endTransmission() != 0) {
    return false;
  }

  delay(20);
  if (wire_.requestFrom(address_, static_cast<uint8_t>(6)) != 6) {
    return false;
  }

  uint8_t data[6] = {};
  for (uint8_t i = 0; i < sizeof(data); ++i) {
    data[i] = static_cast<uint8_t>(wire_.read());
  }

  if (crc8(data, 2) != data[2] || crc8(data + 3, 2) != data[5]) {
    return false;
  }

  const uint16_t rawTemperature =
      (static_cast<uint16_t>(data[0]) << 8) | data[1];
  const uint16_t rawHumidity =
      (static_cast<uint16_t>(data[3]) << 8) | data[4];
  temperatureC = -45.0f + 175.0f * rawTemperature / 65535.0f;
  humidityRh = 100.0f * rawHumidity / 65535.0f;
  return true;
}

uint8_t Sht30::crc8(const uint8_t *data, uint8_t length) {
  uint8_t crc = 0xFF;
  for (uint8_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x80) ? static_cast<uint8_t>((crc << 1) ^ 0x31)
                         : static_cast<uint8_t>(crc << 1);
    }
  }
  return crc;
}
