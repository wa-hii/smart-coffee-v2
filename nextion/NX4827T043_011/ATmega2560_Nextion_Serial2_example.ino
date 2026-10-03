/*
  ROAST SENSE - Nextion command helpers for ATmega2560

  Wiring used by this project:
    Nextion TX -> ATmega2560 PH0/RXD2 physical pin 8 (Mega header RX2/D17)
    Nextion RX -> ATmega2560 PH1/TXD2 physical pin 9 (Mega header TX2/D16)
    Common GND
  Uses USART2 / Serial2.

  If your current wiring is on D8/D9, read PINS_8_9_IMPORTANT.txt first.
*/
HardwareSerial &NEXTION = Serial2;

void nexEnd() {
  NEXTION.write(0xFF); NEXTION.write(0xFF); NEXTION.write(0xFF);
}
void nexCmd(const String &s) {
  NEXTION.print(s); nexEnd();
}
void nexText(const char *obj, const String &value) {
  NEXTION.print(obj); NEXTION.print(".txt=\""); NEXTION.print(value); NEXTION.print("\""); nexEnd();
}
void nexVal(const char *obj, int value) {
  NEXTION.print(obj); NEXTION.print(".val="); NEXTION.print(value); nexEnd();
}

String eventLine;
void pollNextion() {
  while (NEXTION.available()) {
    char c = (char)NEXTION.read();
    if (c == '\n') {
      eventLine.trim();
      if (eventLine.length()) handleNextionEvent(eventLine);
      eventLine = "";
    } else if (c != '\r') {
      eventLine += c;
    }
  }
}

void handleNextionEvent(const String &evt) {
  if (evt == "EVT:DATA_START") {
    // Start 40-cycle labeled acquisition.
  } else if (evt == "EVT:AI_START") {
    // Start unknown-sample acquisition, then send features to Raspberry Pi 5.
  } else if (evt == "EVT:CAL_START") {
    // Start baseline calibration.
  } else if (evt == "EVT:HOME") {
    nexCmd("page pHome");
  }
}

void setup() {
  Serial.begin(115200);
  NEXTION.begin(9600);
  delay(500);
  nexCmd("page pSplash");
}

void loop() {
  pollNextion();
  // sensor acquisition / state machine here
}

// Examples:
//
// nexCmd("page pDataRun");
// nexText("pDataRun.tSample", "L-MING_B10");
// nexText("pDataRun.tCycle", "CYCLE 01 / 40");
// nexVal("pDataRun.jCycle", 3);
// nexText("pDataRun.tPhase", "PURGING");
// nexText("pDataRun.tRemain", "01:58");
// nexText("pDataRun.tTemp", "25.4 C");
// nexText("pDataRun.tHum", "61 %RH");
//
// AI result:
// nexCmd("page pResult");
// nexText("pResult.tRoast", "MEDIUM");
// nexText("pResult.tRConf", "98.5%");
// nexText("pResult.tOrigin", "MING");
// nexText("pResult.tOConf", "94.2%");
// nexVal("pResult.jLight", 1);
// nexVal("pResult.jMedium", 99);
// nexVal("pResult.jDark", 0);
