#pragma once

#include <stddef.h>
#include <stdint.h>

// Bounded line parser for the ASCII CRLF event protocol emitted by the HMI.
class NextionEventParser {
public:
  NextionEventParser(char *storage, size_t capacity)
      : storage_(storage), capacity_(capacity) {}

  // Returns true exactly once when a complete, non-overflowed line is ready.
  bool feed(uint8_t byte) {
    if (byte == '\n') {
      if (overflowed_) {
        reset();
        return false;
      }
      if (length_ == 0) {
        reset();
        return false;
      }
      storage_[length_] = '\0';
      ready_ = true;
      return true;
    }

    if (byte == '\r') {
      return false;
    }

    // This project deliberately uses an ASCII line protocol from HMI event
    // handlers (prints "EVT:...",0 + CRLF). Nextion's native return packets
    // are binary and end in FF FF FF. Never let those bytes contaminate an
    // event line or accidentally form a valid command.
    if (byte < 0x20 || byte > 0x7E) {
      reset();
      return false;
    }

    if (ready_) {
      // The consumer must take the pending frame before accepting another one.
      return false;
    }

    if (length_ + 1 >= capacity_) {
      overflowed_ = true;
      return false;
    }

    storage_[length_++] = static_cast<char>(byte);
    return false;
  }

  bool take(char *destination, size_t destinationCapacity) {
    if (!ready_ || destination == nullptr || destinationCapacity == 0) {
      return false;
    }

    size_t i = 0;
    while (i + 1 < destinationCapacity && storage_[i] != '\0') {
      destination[i] = storage_[i];
      ++i;
    }
    destination[i] = '\0';
    reset();
    return true;
  }

  void reset() {
    length_ = 0;
    overflowed_ = false;
    ready_ = false;
    if (capacity_ > 0) {
      storage_[0] = '\0';
    }
  }

private:
  char *storage_;
  size_t capacity_;
  size_t length_ = 0;
  bool overflowed_ = false;
  bool ready_ = false;
};
