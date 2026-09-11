#include "actuator.h"

// Inisialisasi variabel statik
bool Actuator::s_reversePolarity = false;  // false: Pin 10 HIGH / Pin 11 LOW; true: Pin 11 HIGH / Pin 10 LOW
bool Actuator::s_normallyHigh = true;      // Purging = HIGH, Collecting = LOW
bool Actuator::s_valveState = false;       // status fisik valve: false=OFF (0V), true=ON (+Vs)

void Actuator::begin() {
    pinMode(PIN_VALVE_A, OUTPUT);
    pinMode(PIN_VALVE_B, OUTPUT);
    digitalWrite(PIN_VALVE_A, LOW);
    digitalWrite(PIN_VALVE_B, LOW);
    s_valveState = false;

    // Startup / Idle: valve OFF
    stop();
}

void Actuator::setForward() {
    // Forward: Pin A (Pin 10) = HIGH, Pin B (Pin 11) = LOW
    digitalWrite(PIN_VALVE_B, LOW);
    digitalWrite(PIN_VALVE_A, HIGH);
    s_valveState = true;
}

void Actuator::setReverse() {
    // Reverse: Pin B (Pin 11) = HIGH, Pin A (Pin 10) = LOW
    digitalWrite(PIN_VALVE_A, LOW);
    digitalWrite(PIN_VALVE_B, HIGH);
    s_valveState = true;
}

void Actuator::valveOn() {
    if (!s_reversePolarity) {
        setForward();
    } else {
        setReverse();
    }
}

void Actuator::valveOff() {
    // Kedua pin LOW -> Valve OFF (0V)
    digitalWrite(PIN_VALVE_A, LOW);
    digitalWrite(PIN_VALVE_B, LOW);
    s_valveState = false;
}

void Actuator::toggle() {
    if (s_valveState) {
        valveOff();
    } else {
        valveOn();
    }
}

bool Actuator::isValveOn() {
    return s_valveState;
}

// ═════════════════════════════════════════════════════════════════════════════
// Logika Valve Siklus Akuisisi:
// Collecting (Hisap Sampel) = Valve LOW
// Purging (Udara Bersih)    = Valve HIGH
// Idle / Stop               = Valve OFF (LOW)
// ═════════════════════════════════════════════════════════════════════════════

void Actuator::setCollecting() {
    if (s_normallyHigh) {
        valveOff();   // Saat collecting: valve LOW (0V)
    } else {
        valveOn();
    }
}

void Actuator::setPurging() {
    if (s_normallyHigh) {
        valveOn();    // Saat purging: valve HIGH (Pin 10 HIGH, Pin 11 LOW)
    } else {
        valveOff();
    }
}

void Actuator::stop() {
    // Idle / Stop state: matikan valve (LOW) agar solenoid tidak panas terus-menerus
    valveOff();
}

void Actuator::setDirectPin10(bool high) {
    digitalWrite(PIN_VALVE_A, high ? HIGH : LOW);
}

void Actuator::setDirectPin11(bool high) {
    digitalWrite(PIN_VALVE_B, high ? HIGH : LOW);
}

void Actuator::swapPolarity() {
    s_reversePolarity = !s_reversePolarity;
    if (s_valveState) {
        valveOn();
    }
}

bool Actuator::isReversed() {
    return s_reversePolarity;
}

void Actuator::invertPhase() {
    s_normallyHigh = !s_normallyHigh;
    stop();
}

bool Actuator::isNormallyHigh() {
    return s_normallyHigh;
}

