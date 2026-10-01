#include <Arduino.h>
#include <stdio.h>

#include "../src/nextion_event_parser.h"

// Production smoke test: Nextion TX -> Mega RX1 D19, RX -> TX1 D18.
#define NEXTION_SERIAL Serial1
#define NEXTION_BAUD 115200

static char eventStorage[64] = {};
static char eventLine[64] = {};
static NextionEventParser eventParser(eventStorage, sizeof(eventStorage));

static void sendTerminator() {
  NEXTION_SERIAL.write(0xFF);
  NEXTION_SERIAL.write(0xFF);
  NEXTION_SERIAL.write(0xFF);
}

static void sendCommand(const char *command) {
  NEXTION_SERIAL.print(command);
  sendTerminator();
  Serial.print(F("[NEXTION TX] "));
  Serial.println(command);
}

static void pollNextion() {
  while (NEXTION_SERIAL.available()) {
    if (eventParser.feed(static_cast<uint8_t>(NEXTION_SERIAL.read())) &&
        eventParser.take(eventLine, sizeof(eventLine))) {
      Serial.print(F("[NEXTION RX] "));
      Serial.println(eventLine);
    }
  }
}

static const char *const pages[] = {"pHome", "pTake", "pTest", "pHome"};
static constexpr uint8_t PAGE_COUNT = sizeof(pages) / sizeof(pages[0]);
static uint8_t pageIndex = 1;
static uint32_t nextPageAt = 0;
static bool sequenceDone = false;

void setup() {
  Serial.begin(115200);
  NEXTION_SERIAL.begin(NEXTION_BAUD);

  Serial.println(F("[BOOT] Nextion Serial1 smoke test"));
  Serial.println(F("[BOOT] TX=D18 RX=D19 baud=115200"));
  delay(3000);
  sendCommand("page pHome");
  nextPageAt = millis() + 3000UL;
}

void loop() {
  pollNextion();

  if (!sequenceDone && millis() >= nextPageAt) {
    if (pageIndex < PAGE_COUNT) {
      char command[20] = {};
      snprintf(command, sizeof(command), "page %s", pages[pageIndex]);
      sendCommand(command);
      ++pageIndex;
      nextPageAt = millis() + 3000UL;
    } else {
      Serial.println(F("[TEST] Page sequence complete"));
      Serial.println(F("[TEST] Touch the panel and inspect EVT:* lines"));
      sequenceDone = true;
    }
  }
}
