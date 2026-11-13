// UART0/Nextion Serial2 diagnostic firmware; COMPILE-ONLY until onsite SOP.
// NEVER use as production RF500 firmware.
// Serial0=115200 USB FT232R, Serial2=9600 Nextion.
// No Wire, sensor initialization, EEPROM access or pump/valve ON logic.
#include <Arduino.h>
#include <string.h>

#ifndef USART_BOOT_DIAG_ONLY
#error "Diagnostic only: build via scripts/platformio_uart_nextion_diag.ini"
#endif

static constexpr uint8_t VALVE_IN3 = 10;  // must confirm against SECOND PCB
static constexpr uint8_t VALVE_IN4 = 11;  // both LOW => solenoid disabled
static constexpr uint32_t HOME_FIRST_MS = 3200UL;
static constexpr uint32_t HOME_RETRY_MS = 10000UL;
static constexpr uint32_t HEARTBEAT_MS = 5000UL;
static constexpr char BUILD_ID[] = "uart-nextion-bench-20261113";
static char command[24] = {};
static uint8_t index = 0;
static uint8_t pageAttempts = 0;
static uint32_t lastPage = 0;
static uint32_t lastHeartbeat = 0;
static bool started = false;
static bool nextionReplySeen = false;
static uint8_t lastReportedPage = 255;
static uint8_t replyParserState = 0;
static uint8_t replyPage = 255;

static void nextionEnd() {
  Serial2.write(0xff);
  Serial2.write(0xff);
  Serial2.write(0xff);
}

static void sendHome() {
  Serial2.print(F("page pHome"));
  nextionEnd();
  // Documented, non-control Nextion query: 0x66 <page-id> FF FF FF.
  // This confirms whether the LCD actually parsed an incoming UART command.
  Serial2.print(F("sendme"));
  nextionEnd();
  ++pageAttempts;
  lastPage = millis();
  Serial.print(F("{\"event\":\"UART_DIAG\",\"stage\":\"HOME_COMMAND_TX\",\"try\":"));
  Serial.print(pageAttempts);
  Serial.println(F(",\"confirmed_by_lcd\":false}"));
}

static void pollNextion() {
  while (Serial2.available()) {
    const uint8_t byte = static_cast<uint8_t>(Serial2.read());
    if (replyParserState == 0) {
      if (byte == 0x66) replyParserState = 1;
      continue;
    }
    if (replyParserState == 1) {
      replyPage = byte;
      replyParserState = 2;
      continue;
    }
    if (byte != 0xff) {
      replyParserState = byte == 0x66 ? 1 : 0;
      continue;
    }
    ++replyParserState;
    if (replyParserState == 5) {
      lastReportedPage = replyPage;
      nextionReplySeen = true;
      replyParserState = 0;
      Serial.print(F("{\"event\":\"UART_DIAG\",\"stage\":\"NEXTION_PAGE_REPLY\",\"page_id\":"));
      Serial.print(lastReportedPage);
      Serial.println(lastReportedPage == 1 && pageAttempts > 0
                         ? F(",\"home_verified\":true}")
                         : F(",\"home_verified\":false}"));
    }
  }
}

static void replyStatus() {
  Serial.print(F("{\"event\":\"UART_DIAG\",\"stage\":\"STATUS_REPLY\",\"build_id\":\""));
  Serial.print(BUILD_ID);
  Serial.print(F("\",\"uptime_ms\":"));
  Serial.print(millis());
  Serial.print(F(",\"pHome_attempts\":"));
  Serial.print(pageAttempts);
  Serial.print(F(",\"nextion_page_reply_seen\":"));
  Serial.print(nextionReplySeen ? F("true") : F("false"));
  Serial.print(F(",\"nextion_page_id\":"));
  Serial.print(lastReportedPage);
  Serial.println(F(",\"sensor_initialized\":false,\"d10_d11_low\":true}"));
}

static void serialPoll() {
  while (Serial.available()) {
    const char c = static_cast<char>(Serial.read());
    if (c == '#' && index == 0) {
      command[index++] = c;
      continue;
    }
    if (index == 0) continue;
    if (c == ';') {
      command[index] = '\0';
      if (strcmp(command, "#status") == 0 || strcmp(command, "#help") == 0) {
        replyStatus();
      } else {
        Serial.println(F("{\"event\":\"UART_DIAG\",\"stage\":\"COMMAND_REJECTED\"}"));
      }
      index = 0;
      continue;
    }
    if (index >= sizeof(command) - 1 || c == '\n' || c == '\r') {
      index = 0;  // fail-closed, no actuator or data acquisition commands
      continue;
    }
    command[index++] = c;
  }
}

void setup() {
  // Set output levels LOW before making pins outputs; never energize coil.
  digitalWrite(VALVE_IN3, LOW);
  digitalWrite(VALVE_IN4, LOW);
  pinMode(VALVE_IN3, OUTPUT);
  pinMode(VALVE_IN4, OUTPUT);

  Serial.begin(115200);
  Serial2.begin(9600);
  Serial2.print(F("bkcmd=0"));
  nextionEnd();
  Serial.print(F("{\"event\":\"UART_DIAG\",\"stage\":\"BOOT\",\"build_id\":\""));
  Serial.print(BUILD_ID);
  Serial.println(F("\",\"serial0_baud\":115200,\"nextion_serial2_baud\":9600,\"no_i2c\":true}"));
  started = true;
}

void loop() {
  if (!started) return;
  serialPoll();
  pollNextion();
  const uint32_t now = millis();
  if (pageAttempts == 0 && now >= HOME_FIRST_MS) {
    sendHome();
  } else if (pageAttempts > 0 && pageAttempts < 3 &&
             now - lastPage >= HOME_RETRY_MS) {
    sendHome();
  }
  if (now - lastHeartbeat >= HEARTBEAT_MS) {
    lastHeartbeat = now;
    Serial.print(F("{\"event\":\"UART_DIAG\",\"stage\":\"HEARTBEAT\",\"uptime_ms\":"));
    Serial.print(now);
    Serial.println(F(",\"d10_d11_low\":true}"));
  }
}
