// ═════════════════════════════════════════════════════════════════════════════
// actuator.h — Modul Aktuator (2× Solenoid Valve Festo 3/2-way)
// Festo MHE2-MS1H-3/2G-M7 — 24V DC, normally closed
// Dikendalikan via relay/MOSFET dari pin digital ATmega 2560
// ═════════════════════════════════════════════════════════════════════════════
#pragma once
#include <Arduino.h>

// ─── Pin Digital pada ATmega 2560 ─────────────────────────────────────────────
#define PIN_VALVE1  14   // Solenoid valve 1 — aliran ke sampel kopi
#define PIN_VALVE2  19   // Solenoid valve 2 — aliran ke udara bersih (purge)

// ═══════════════════════════════════════════════════════════════════════════════
class Actuator {
public:
    void begin();           // pinMode OUTPUT, semua OFF
    void setCollecting();   // V1 ON (sampel), V2 OFF → hisap aroma kopi
    void setPurging();      // V1 OFF, V2 ON → hisap udara bersih (baseline)
    void stop();            // semua OFF
};
