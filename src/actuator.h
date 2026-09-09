#pragma once
#include <Arduino.h>

// ─── Valve Festo MHE2-MS1H-3/2G-M7 via L293DD ────────────────────────────────
//
// Wiring L293DD ke ATmega2560 (Confirmed via #pin_scan):
//   Arduino Pin 10 (PB4, IC Pin 23) → L293DD IN3
//   Arduino Pin 11 (PB5, IC Pin 24) → L293DD IN4
//
// Festo Valve terhubung melintang antara OUT3 dan OUT4.
// Karena sifat polaritas koil, kita harus memberikan beda potensial
// (satu sisi HIGH, satu sisi LOW) untuk menghidupkan solenoid (Collecting).
// Untuk mematikan (Purging/Stop), kedua sisi diberikan LOW.
// ─────────────────────────────────────────────────────────────────────────────
#define PIN_L293_IN3 10
#define PIN_L293_IN4 11

// Opsi Polaritas:
// Jika saat collecting valve tidak klik, ubah REVERSE_POLARITY menjadi 1
#define REVERSE_POLARITY 0

// ═══════════════════════════════════════════════════════════════════════════════
class Actuator {
public:
  void begin();         // pinMode OUTPUT, solenoid OFF (posisi purge/spring)
  void setCollecting(); // Solenoid ON  → Port 1/33 buka → hisap aroma kopi
  void setPurging();    // Solenoid OFF → Port 3/11 buka → hisap udara bersih
  void stop();          // Solenoid OFF → posisi aman (purge / spring return)
};
