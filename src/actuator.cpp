#include "actuator.h"

void Actuator::begin() {
    pinMode(PIN_VALVE1, OUTPUT);
    pinMode(PIN_VALVE2, OUTPUT);
    stop();   // pastikan semua OFF saat boot
}

void Actuator::setCollecting() {
    // Valve 1 ON → buka jalur ke sampel kopi
    // Valve 2 OFF → tutup jalur udara bersih
    digitalWrite(PIN_VALVE1, HIGH);
    digitalWrite(PIN_VALVE2, LOW);
}

void Actuator::setPurging() {
    // Valve 1 OFF → tutup jalur ke sampel
    // Valve 2 ON → buka jalur udara bersih
    digitalWrite(PIN_VALVE1, LOW);
    digitalWrite(PIN_VALVE2, HIGH);
}

void Actuator::stop() {
    // fa ada aliran
    digitalWrite(PIN_VALVE1, LOW);
    digitalWrite(PIN_VALVE2, LOW);
}
