// ─────────────────────────────────────────────────────────────────────────────
// actuator.cpp — Kontrol Valve Festo MHE2-MS1H-3/2G-M7 via L293DD
//
// Valve 3/2-way dikontrol secara differential menggunakan L293DD:
//   COLLECTING: Memberi beda potensial pada kumparan (IN3 = HIGH, IN4 = LOW)
//   PURGING   : Mengosongkan tegangan pada kumparan (IN3 = LOW, IN4 = LOW),
//               mengandalkan spring return untuk pindah ke port purge.
// ─────────────────────────────────────────────────────────────────────────────
#include "actuator.h"

// ─────────────────────────────────────────────────────────────────────────────
void Actuator::begin() {
    pinMode(PIN_L293_IN3, OUTPUT);
    pinMode(PIN_L293_IN4, OUTPUT);
    stop();   // solenoid OFF saat boot → posisi purge (aman)
}

// ─────────────────────────────────────────────────────────────────────────────
void Actuator::setCollecting() {
    // Memberikan beda tegangan pada L293DD untuk menggerakkan valve
#if REVERSE_POLARITY
    digitalWrite(PIN_L293_IN3, LOW);
    digitalWrite(PIN_L293_IN4, HIGH);
#else
    digitalWrite(PIN_L293_IN3, HIGH);
    digitalWrite(PIN_L293_IN4, LOW);
#endif
}

// ─────────────────────────────────────────────────────────────────────────────
void Actuator::setPurging() {
    // Solenoid OFF (keduanya LOW) → spring return → Port 2 ↔ Port 3/11 terbuka
    // Pompa menghisap udara bersih → membilas sensor dari aroma residual
    digitalWrite(PIN_L293_IN3, LOW);
    digitalWrite(PIN_L293_IN4, LOW);
}

// ─────────────────────────────────────────────────────────────────────────────
void Actuator::stop() {
    // Solenoid OFF → posisi aman (fresh air, tidak ada aroma dari sampel)
    digitalWrite(PIN_L293_IN3, LOW);
    digitalWrite(PIN_L293_IN4, LOW);
}
