#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string>
#define F(x) x
// Host-only UART mock: verify exact wire bytes and availableForWrite guard.
class HardwareSerial {
public:
  int free = 63;
  std::string wire;
  void begin(uint32_t) {}
  int available() { return 0; }
  int read() { return -1; }
  int availableForWrite() { return free; }
  void print(const char *s) { wire += s; }
  void print(char c) { wire += c; }
  void print(long n) { wire += std::to_string(n); }
  void print(int n) { print((long)n); }
  void print(uint8_t n) { print((long)n); }
  size_t write(uint8_t n) { wire += (char)n; return 1; }
  size_t write(const uint8_t *p, size_t n) {
    wire.append(reinterpret_cast<const char *>(p), n); return n;
  }
};
