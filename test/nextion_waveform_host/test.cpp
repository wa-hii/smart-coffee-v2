#include <cassert>
#include <iostream>
#include "nextion_transport.h"
#include "nextion_waveform.h"

int main() {
  using namespace NextionWaveform;
  assert(scale(0, DATA_HEIGHT) == 0);
  assert(scale(32767, DATA_HEIGHT) == 78);
  assert(scale(32767, TEST_HEIGHT) == 45);
  assert(scale(16384, DATA_HEIGHT) == 39);
  assert(scale(65535, DATA_HEIGHT) == 0);
  assert(scale(12345, 0) == 0);
  for (uint32_t raw = 1; raw <= 32767; ++raw) {
    assert(scale(raw, DATA_HEIGHT) >= scale(raw - 1, DATA_HEIGHT));
    assert(scale(raw, TEST_HEIGHT) <= 45);
  }
  HardwareSerial serial;
  NextionTransport t(serial);
  const uint8_t values[4] = {0, 1, 39, 78};
  const std::string end(3, (char)0xFF);
  const std::string expected = "add 11,0,0" + end + "add 11,1,1" + end
      + "add 11,2,39" + end + "add 11,3,78" + end;
  serial.free = expected.size() - 1;
  assert(!t.tryWaveformFrame(DATA_ID, values));
  assert(serial.wire.empty());
  serial.free = expected.size();
  assert(t.tryWaveformFrame(DATA_ID, values));
  assert(serial.wire == expected);
  serial.wire.clear();
  const uint8_t maxValues[4] = {255,255,255,255};
  serial.free = 63;
  assert(t.tryWaveformFrame(TEST_ID, maxValues));
  assert(serial.wire.size() == 60);
  serial.wire.clear();
  t.clearWaveform(TEST_ID);
  assert(serial.wire == "cle 10,255" + end);
  std::cout << "NEXTION_WAVEFORM_HOST_PASS\n";
}
