#pragma once

#include <Arduino.h>

#include "nextion_event_parser.h"

class NextionTransport {
public:
  using EventHandler = void (*)(const char *event);

  explicit NextionTransport(HardwareSerial &serial);

  void begin(uint32_t baud);
  void poll(EventHandler handler);

  void command(const char *value);
  void page(const char *pageName);
  void text(const char *object, const char *value);
  void value(const char *object, int value);
  void progress(const char *object, uint8_t percent);
  void touch(const char *object, bool enabled);
  void textColor(const char *object, uint16_t color);

private:
  static constexpr size_t EVENT_CAPACITY = 64;
  static constexpr size_t TEXT_CAPACITY = 96;

  void terminator();
  void safeText(const char *value);
  void numericAttribute(const char *object, const char *attribute, long value);

  HardwareSerial &serial_;
  char eventStorage_[EVENT_CAPACITY] = {};
  char event_[EVENT_CAPACITY] = {};
  NextionEventParser parser_{eventStorage_, sizeof(eventStorage_)};
};
