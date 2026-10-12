// Isolated Arduino Mega 2560 Serial1 <-> Pi 5 UART bench.
// NO pumps, valves, sensor excitation, calibration, EEPROM or other GPIO.
// USB Serial: diagnostics to operator laptop, Serial1 D18/D19: bench UART.
#include <Arduino.h>
#include <string.h>

constexpr uint32_t USB_DEBUG_BAUD = 115200;
constexpr uint32_t PI_UART_BAUD = 9600;
constexpr uint32_t HEARTBEAT_MS = 1000;
constexpr uint8_t INPUT_MAX = 40;
constexpr uint32_t PROTOCOL_VERSION = 1;

uint32_t seq = 0;
uint32_t previousHeartbeat = 0;
char input[INPUT_MAX + 1];
uint8_t inputIndex = 0;
bool inputOverflow = false;

void heartbeat(uint32_t now) {
  Serial1.print(F("{\"type\":\"heartbeat\",\"proto\":1,\"seq\":"));
  Serial1.print(++seq);
  Serial1.print(F(",\"uptime_ms\":"));
  Serial1.print(now);
  Serial1.println(F("}"));

  Serial.print(F("HEARTBEAT "));
  Serial.println(seq);
}

bool validNonce(const char *value) {
  size_t length = strlen(value);
  if (length == 0 || length > 16) return false;
  for (size_t i = 0; i < length; ++i) {
    bool digit = value[i] >= '0' && value[i] <= '9';
    bool upper = value[i] >= 'A' && value[i] <= 'F';
    if (!digit && !upper) return false;
  }
  return true;
}

void handleInput(char *line) {
  // Only accepted command: PING,<1..16 uppercase hexadecimal chars>.
  // Unknown and malformed commands have NO actuator side effect.
  if (strncmp(line, "PING,", 5) != 0) return;
  const char *nonce = line + 5;
  if (!validNonce(nonce)) return;
  Serial1.print(F("{\"type\":\"pong\",\"proto\":1,\"nonce\":\""));
  Serial1.print(nonce);
  Serial1.println(F("\"}"));
  Serial.println(F("PING ACK"));
}

void pollInput() {
  while (Serial1.available() > 0) {
    const char c = (char)Serial1.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!inputOverflow && inputIndex > 0) {
        input[inputIndex] = 0;
        handleInput(input);
      }
      inputIndex = 0;
      inputOverflow = false;
    } else if (!inputOverflow) {
      if (inputIndex >= INPUT_MAX) {
        inputOverflow = true;
      } else {
        input[inputIndex++] = c;
      }
    }
  }
}

void setup() {
  Serial.begin(USB_DEBUG_BAUD);
  Serial1.begin(PI_UART_BAUD);
  Serial.println(F("MEGA_PI_UART_BENCH_V1 READY"));
  // First heartbeat after 1s; no command needed to start the bench.
  previousHeartbeat = millis();
}

void loop() {
  pollInput();
  const uint32_t now = millis();
  if ((uint32_t)(now - previousHeartbeat) >= HEARTBEAT_MS) {
    previousHeartbeat += HEARTBEAT_MS;
    heartbeat(now);
  }
}
