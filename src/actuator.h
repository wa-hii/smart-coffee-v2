#pragma once
#include <Arduino.h>
#include <avr/io.h>

// ═════════════════════════════════════════════════════════════════════════════
// Konfigurasi Valve Festo 3/2 via Driver (L293DD / Relay / H-Bridge):
//
// Sambungan ke ATmega 2560:
//   - Pin 10 ATmega2560 ──► Pin A (IN1 Driver Valve)
//   - Pin 11 ATmega2560 ──► Pin B (IN2 Driver Valve)
//
// Mode Operasi:
//   - PURGING    : Valve HIGH (Pin 10 HIGH, Pin 11 LOW) -> Udara Bersih
//   - COLLECTING : Valve LOW  (Pin 10 LOW,  Pin 11 LOW) -> Sampel Kopi
//   - IDLE / STOP: Valve OFF  (Pin 10 LOW,  Pin 11 LOW)
// ═════════════════════════════════════════════════════════════════════════════

#define PIN_VALVE_A     10   // Pin 10 ATmega2560 (Pin A)
#define PIN_VALVE_B     11   // Pin 11 ATmega2560 (Pin B)

// Backward compatibility alias
#define PIN_L293D_IN3   PIN_VALVE_A
#define PIN_L293D_IN4   PIN_VALVE_B

class Actuator {
public:
    static void begin();           // Inisialisasi pin 10 & 11 (OUTPUT, LOW)
    
    // Kontrol Alur Akuisisi E-Nose
    static void setCollecting();   // Fase Collecting: Valve LOW (0V)
    static void setPurging();      // Fase Purging: Valve HIGH (Pin 10 HIGH, Pin 11 LOW)
    static void stop();            // Default idle state: Valve OFF (0V)

    // Kontrol Langsung Valve
    static void valveOn();         // Solenoid ON (Pin 10 HIGH, Pin 11 LOW)
    static void valveOff();        // Solenoid OFF (Pin 10 LOW, Pin 11 LOW)
    static void toggle();          // Toggle state
    static bool isValveOn();

    // H-Bridge Direction
    static void setForward();      // Pin 10 HIGH, Pin 11 LOW
    static void setReverse();      // Pin 11 HIGH, Pin 10 LOW
    static void swapPolarity();    // Tukar arah polaritas jika kabel terbalik
    static bool isReversed();

    // Invert Mode Normally High vs Normally Low
    static void invertPhase();
    static bool isNormallyHigh();

    // Direct Pin Test
    static void setDirectPin10(bool high);
    static void setDirectPin11(bool high);
    static void setDirectPin19(bool high) { setDirectPin10(high); }
    static void setDirectPin20(bool high) { setDirectPin11(high); }

private:
    static bool s_reversePolarity;
    static bool s_normallyHigh;    // Default: true (Purging = HIGH, Collecting = LOW)
    static bool s_valveState;
};
