#ifndef NEXTION_TRANSPORT_H
#define NEXTION_TRANSPORT_H

#include <Arduino.h>

class NextionTransport {
public:
  explicit NextionTransport(HardwareSerial &serial)
      : _serial(serial), _bufIdx(0) {
    _buffer[0] = '\0';
  }

  void begin(unsigned long baud) {
    _serial.begin(baud);
    _bufIdx = 0;
    _buffer[0] = '\0';
  }

  void command(const char *cmd) {
    if (!cmd) return;
    _serial.print(cmd);
    endCmd();
  }

  void page(const char *pageName) {
    if (!pageName) return;
    _serial.print(F("page "));
    _serial.print(pageName);
    endCmd();
  }

  void text(const char *component, const char *value) {
    if (!component || !value) return;
    _serial.print(component);
    _serial.print(F(".txt=\""));
    _serial.print(value);
    _serial.print(F("\""));
    endCmd();
  }

  void textColor(const char *component, uint16_t color) {
    if (!component) return;
    _serial.print(component);
    _serial.print(F(".pco="));
    _serial.print(color);
    endCmd();
  }

  void touch(const char *component, bool enable) {
    if (!component) return;
    _serial.print(F("tsw "));
    _serial.print(component);
    _serial.print(enable ? F(",1") : F(",0"));
    endCmd();
  }

  void progress(const char *component, uint8_t value) {
    if (!component) return;
    _serial.print(component);
    _serial.print(F(".val="));
    _serial.print(value);
    endCmd();
  }

  void poll(void (*handler)(const char *event)) {
    if (!handler) return;

    while (_serial.available()) {
      int c = _serial.read();
      if (c < 0) break;
      uint8_t b = static_cast<uint8_t>(c);

      // Nextion command terminator is 0xFF 0xFF 0xFF, or standard \r \n
      if (b == 0xFF || b == '\n' || b == '\r') {
        if (_bufIdx > 0) {
          _buffer[_bufIdx] = '\0';
          handler(_buffer);
          _bufIdx = 0;
          _buffer[0] = '\0';
        }
      } else {
        // Discard binary junk / sync until 'E' for "EVT:" protocol
        if (_bufIdx == 0 && b != 'E') {
          continue;
        }
        if (_bufIdx < sizeof(_buffer) - 1) {
          _buffer[_bufIdx++] = static_cast<char>(b);
        } else {
          _bufIdx = 0;
          _buffer[0] = '\0';
        }
      }
    }
  }

private:
  void endCmd() {
    _serial.write(0xFF);
    _serial.write(0xFF);
    _serial.write(0xFF);
  }

  HardwareSerial &_serial;
  char _buffer[64];
  size_t _bufIdx;
};

#endif // NEXTION_TRANSPORT_H
