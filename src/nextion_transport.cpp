#include "nextion_transport.h"

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
