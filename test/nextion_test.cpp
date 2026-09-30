// ═══════════════════════════════════════════════════════════════════════════════
// nextion_test.cpp — Nextion UART2 Communication Test
// ATmega2560 ↔ Nextion NX4827T043_011
//
// Compile : pio run -e nextion_test
// Upload  : pio run -e nextion_test -t upload
// Monitor : pio device monitor -e nextion_test
// Revert  : pio run -e mega2560 -t upload
//
// Wiring (sesuai PCB/schematic aktual — UART2):
//   Nextion VCC → supply 5V eksternal (BUKAN dari pin 5V Arduino)
//   Nextion GND → ATmega GND  ← common ground WAJIB
//   Nextion TX  → ATmega RXD2 / PH0 / Arduino pin 17
//   Nextion RX  → ATmega TXD2 / PH1 / Arduino pin 16
//
// SAFETY:
//   - Nextion butuh 5V stabil; gunakan supply eksternal.
//   - TX → RX, RX → TX (jangan terbalik).
//   - Minimum 4.75 V ke Nextion; jangan 3.3 V.
// ═══════════════════════════════════════════════════════════════════════════════

#include <Arduino.h>

// ─── Nextion UART (Serial2 = RXD2/PH0 = D17, TXD2/PH1 = D16) ────────────────
#define NEXTION_SERIAL  Serial2
// Baud default Nextion dari pabrik = 9600.
// NextionInterface::init() juga menggunakan 9600 (lihat lib/NextionInterface/NextionInterface.h:95).
// Gunakan 9600 kecuali HMI sudah dikonfigurasi ulang secara eksplisit ke nilai lain.
#define NEXTION_BAUD    9600

// ─── Nextion Command Helpers ─────────────────────────────────────────────────

/** Kirim 3-byte terminator 0xFF 0xFF 0xFF */
static void nexEnd() {
    NEXTION_SERIAL.write(0xFF);
    NEXTION_SERIAL.write(0xFF);
    NEXTION_SERIAL.write(0xFF);
}

/** Kirim perintah Nextion + terminator + log ke Serial Monitor */
static void nexCmd(const char* cmd) {
    NEXTION_SERIAL.print(cmd);
    nexEnd();
    Serial.print(F("[NEXTION] TX: "));
    Serial.println(cmd);
}

// ─── Nextion Event Parser (non-blocking) ─────────────────────────────────────
static String _nxLine;

static void handleNextionEvent(const String& evt) {
    Serial.print(F("[NEXTION RX] "));
    Serial.println(evt);
}

/** Dipanggil setiap loop() — baca byte per byte, selesai saat '\n' */
static void pollNextion() {
    while (NEXTION_SERIAL.available()) {
        char c = (char)NEXTION_SERIAL.read();
        if (c == '\n') {
            _nxLine.trim();
            if (_nxLine.length() > 0) handleNextionEvent(_nxLine);
            _nxLine = "";
        } else if (c != '\r') {
            _nxLine += c;
        }
    }
}

// ─── Test Sequence: pHome → pTake → pTest → pHome (timed, sekali jalan) ──────
static const uint8_t  PAGES[]     = { 0, 1, 2, 3 };  // index ke pageNames[]
static const char* const pageNames[] = { "pHome", "pTake", "pTest", "pHome" };
static const uint8_t  TOTAL_STEPS = 4;

static uint8_t  testStep   = 0;
static uint32_t testNextMs = 0;
static bool     testDone   = false;

// ─── setup() ─────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000) {}  // tunggu host (USB CDC)

    Serial.println(F(""));
    Serial.println(F("═══════════════════════════════════════════════════════"));
    Serial.println(F("[BOOT] ATmega started"));
    Serial.println(F("[BOOT] Nextion UART2 Test — NX4827T043_011"));
    Serial.println(F("═══════════════════════════════════════════════════════"));

    // Inisialisasi Serial2 sesuai wiring PCB aktual (RXD2/TXD2)
    NEXTION_SERIAL.begin(NEXTION_BAUD);

    Serial.println(F("[NEXTION] Serial2 initialized"));
    Serial.print  (F("[NEXTION] Baud: "));
    Serial.println(NEXTION_BAUD);

    // Tunggu Nextion selesai boot (pSplash "Initializing..." selesai)
    Serial.println(F("[NEXTION] Waiting 3 s for Nextion boot..."));
    delay(3000);

    // Kirim command pertama: pindah dari pSplash ke pHome
    nexCmd("page pHome");

    Serial.println(F(""));
    Serial.println(F("[TEST] Visual page sequence: pHome → pTake → pTest → pHome"));
    Serial.println(F("[TEST] Interval antar page: 3 detik"));
    Serial.println(F(""));

    // step 0 sudah dikirim (pHome), lanjutkan ke step berikutnya setelah 3 s
    testStep   = 1;
    testNextMs = millis() + 3000;
}

// ─── loop() ──────────────────────────────────────────────────────────────────
void loop() {
    // Poll RX dari Nextion (non-blocking)
    pollNextion();

    // Kirim page berikutnya sesuai jadwal
    if (!testDone && millis() >= testNextMs) {
        if (testStep < TOTAL_STEPS) {
            nexCmd(pageNames[testStep]);
            testStep++;
            testNextMs = millis() + 3000;
        } else {
            // Sequence selesai — laporan final
            Serial.println(F(""));
            Serial.println(F("═══════════════════════════════════════════════════════"));
            Serial.println(F("[TEST] Sequence selesai: pHome → pTake → pTest → pHome"));
            Serial.println(F("[TEST] Tekan tombol di Nextion untuk uji EVT (RX):"));
            Serial.println(F("  EVT:TAKE_OPEN  — Take Data (pHome)"));
            Serial.println(F("  EVT:DATA_START — Start (pTake)"));
            Serial.println(F("  EVT:TEST_START — Start Test (pHome)"));
            Serial.println(F("  EVT:AI_START   — Start AI (pTest)"));
            Serial.println(F("═══════════════════════════════════════════════════════"));
            testDone = true;
        }
    }
}
