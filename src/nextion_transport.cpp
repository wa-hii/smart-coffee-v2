#include "nextion_transport.h"

#include <string.h>
#include <stdio.h>

NextionTransport::NextionTransport(HardwareSerial &serial) : serial_(serial) {}

void NextionTransport::begin(uint32_t baud) { serial_.begin(baud); }

void NextionTransport::poll(EventHandler handler) {
  while (serial_.available()) {
    if (parser_.feed(static_cast<uint8_t>(serial_.read()))) {
      if (parser_.take(event_, sizeof(event_)) && handler != nullptr) {
        handler(event_);
      }
    }
  }
}

void NextionTransport::terminator() {
  serial_.write(0xFF);
  serial_.write(0xFF);
  serial_.write(0xFF);
}

void NextionTransport::command(const char *value) {
  if (value == nullptr) {
    return;
  }
  serial_.print(value);
  terminator();
}

void NextionTransport::page(const char *pageName) {
  serial_.print(F("page "));
  command(pageName);
}

void NextionTransport::safeText(const char *value) {
  if (value == nullptr) {
    return;
  }

  size_t written = 0;
  while (*value != '\0' && written + 1 < TEXT_CAPACITY) {
    const char c = *value++;
    // Prevent a value from escaping the quoted Nextion text command.
    if (c == '"' || c == '\\' || c < 0x20 || c == 0x7F) {
      serial_.print(' ');
    } else {
      serial_.print(c);
    }
    ++written;
  }
}

void NextionTransport::text(const char *object, const char *value) {
  if (object == nullptr) {
    return;
  }
  serial_.print(object);
  serial_.print(F(".txt=\""));
  safeText(value);
  serial_.print('"');
  terminator();
}

bool NextionTransport::tryText(const char *object, const char *value) {
  if (object == nullptr || value == nullptr) {
    return false;
  }
  // .txt=" + closing quote + 0xFF x3 = ten framing bytes.
  const size_t len = strlen(value);
  const size_t capped = len < TEXT_CAPACITY - 1 ? len : TEXT_CAPACITY - 1;
  const size_t needed = strlen(object) + capped + 10;
  if (needed > 63 || serial_.availableForWrite() < static_cast<int>(needed)) {
    return false;
  }
  text(object, value);
  return true;
}

bool NextionTransport::tryProgress(const char *object, uint8_t percent) {
  if (object == nullptr) {
    return false;
  }
  // .val= + up to 3 digits + 0xFF x3 = eleven framing bytes.
  const size_t needed = strlen(object) + 11;
  if (needed > 63 || serial_.availableForWrite() < static_cast<int>(needed)) {
    return false;
  }
  progress(object, percent);
  return true;
}

bool NextionTransport::tryWaveformFrame(uint8_t id,
                                        const uint8_t (&values)[4]) {
  // Reserve the entire four-channel frame before sending any bytes.
  // No partial frame, blocking write or transparent serial mode.
  char frame[60];
  size_t used = 0;
  for (uint8_t ch = 0; ch < 4; ++ch) {
    const int n = snprintf(frame + used, sizeof(frame) - used,
                           "add %u,%u,%u", (unsigned)id, (unsigned)ch,
                           (unsigned)values[ch]);
    if (n < 0 || used + (size_t)n + 3 > sizeof(frame)) return false;
    used += (size_t)n;
    frame[used++] = (char)0xFF;
    frame[used++] = (char)0xFF;
    frame[used++] = (char)0xFF;
  }
  if (serial_.availableForWrite() < (int)used) return false;
  serial_.write(reinterpret_cast<const uint8_t *>(frame), used);
  return true;
}

void NextionTransport::clearWaveform(uint8_t id) {
  char cmd[16];
  snprintf(cmd, sizeof(cmd), "cle %u,255", (unsigned)id);
  command(cmd);
}

void NextionTransport::value(const char *object, int value) {
  if (object == nullptr) {
    return;
  }
  serial_.print(object);
  serial_.print(F(".val="));
  serial_.print(value);
  terminator();
}

void NextionTransport::progress(const char *object, uint8_t percent) {
  if (object == nullptr) {
    return;
  }
  if (percent > 100) {
    percent = 100;
  }
  value(object, percent);
}

void NextionTransport::numericAttribute(const char *object,
                                        const char *attribute, long value) {
  if (object == nullptr || attribute == nullptr) {
    return;
  }
  serial_.print(object);
  serial_.print('.');
  serial_.print(attribute);
  serial_.print('=');
  serial_.print(value);
  terminator();
}

void NextionTransport::touch(const char *object, bool enabled) {
  if (object == nullptr) {
    return;
  }
  serial_.print(F("tsw "));
  serial_.print(object);
  serial_.print(',');
  serial_.print(enabled ? 1 : 0);
  terminator();
}

void NextionTransport::textColor(const char *object, uint16_t color) {
  numericAttribute(object, "pco", color);
}
