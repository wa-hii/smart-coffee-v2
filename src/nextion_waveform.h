#pragma once
#include <stdint.h>

// IDs reserved by appending a native Waveform to each original page.
// Verify these IDs in the final HMI before deploying the new UI profile.
namespace NextionWaveform {
constexpr uint8_t DATA_ID = 11;
constexpr uint8_t TEST_ID = 10;
constexpr uint8_t DATA_HEIGHT = 79;
constexpr uint8_t TEST_HEIGHT = 46;

// ADS1115 signed positive full scale. Nextion plots values in pixels,
// not automatically rescaled to the object's height.
inline uint8_t scale(uint16_t raw, uint8_t height) {
  if (height < 2 || raw > 32767U) return 0;
  return static_cast<uint8_t>((static_cast<uint32_t>(raw) *
                               (height - 1U) + 16383UL) / 32767UL);
}
}
