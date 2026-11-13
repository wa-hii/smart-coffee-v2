// Wrapper untuk sketch resmi ArduinoISP (BSD), disimpan di private/.
//
// Tujuan wrapper C++: menghindari praproses .ino PlatformIO yang memunculkan
// peringatan makro PIN RESET dan memastikan pin ISP pada Arduino Mega 2560.
// HANYA untuk Mega CH340 COM12, jangan dijalankan pada E-Nose COM11.
#include <Arduino.h>
#include <SPI.h>

#if !defined(__AVR_ATmega2560__)
#error "Programmer harus berupa ATmega2560"
#endif

// Arduino IDE otomatis menghasilkan prototype .ino; wrapper C++ membutuhkannya.
void avrisp();
uint8_t write_flash_pages(int length);
uint8_t write_eeprom_chunk(unsigned int start, unsigned int length);

#include "../../../private/com12_arduino_isp/vendor/ArduinoISP.ino"

// Selalu gunakan D10 untuk RESET target, bukan RESET papan programmer.
#if RESET != 10
#error "ArduinoISP RESET harus D10 pada Arduino Mega2560"
#endif
#if ARDUINOISP_PIN_MISO != MISO || ARDUINOISP_PIN_MOSI != MOSI || ARDUINOISP_PIN_SCK != SCK
#error "ArduinoISP wajib menggunakan SPI hardware ICSP/Mega D50-D52"
#endif
#if BAUDRATE != 19200
#error "ArduinoISP STK500v1 wajib menggunakan 19200 baud"
#endif
