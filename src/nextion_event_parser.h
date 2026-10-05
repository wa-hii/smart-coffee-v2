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
    // Nextion sends the native startup packet 88 FF FF FF after boot/reset.
    // Convert that binary packet into the same bounded ASCII event channel
    // used by the rest of this project. This lets the ATmega recover when the
    // HMI reboots independently (for example after microSD TFT flashing).
    if (startupPacketIndex_ != 0) {
      if (byte == 0xFF) {
        ++startupPacketIndex_;
        if (startupPacketIndex_ == 4) {
          startupPacketIndex_ = 0;
          return emitSynthetic("EVT:HMI_READY");
        }
        return false;
      }

      // Broken startup sequence: discard the native prefix, then allow a
      // printable byte to be parsed normally below.
      startupPacketIndex_ = 0;
    }

    if (byte == 0x88) {
      resetLine();
      startupPacketIndex_ = 1;
      return false;
    }

    if (byte == '\n') {
      if (overflowed_) {
        resetLine();
        return false;
      }
      if (length_ == 0) {
        resetLine();
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
      resetLine();
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
    resetLine();
    return true;
  }

  void reset() {
    resetLine();
    startupPacketIndex_ = 0;
  }

private:
  bool emitSynthetic(const char *event) {
    if (event == nullptr || capacity_ == 0) {
      resetLine();
      return false;
    }

    size_t i = 0;
    while (event[i] != '\0' && i + 1 < capacity_) {
      storage_[i] = event[i];
      ++i;
    }
    if (event[i] != '\0') {
      resetLine();
      return false;
    }
    storage_[i] = '\0';
    length_ = i;
    overflowed_ = false;
    ready_ = true;
    return true;
  }

  void resetLine() {
    length_ = 0;
    overflowed_ = false;
    ready_ = false;
    if (capacity_ > 0) {
      storage_[0] = '\0';
    }
  }

  char *storage_;
  size_t capacity_;
  size_t length_ = 0;
  bool overflowed_ = false;
  bool ready_ = false;
  uint8_t startupPacketIndex_ = 0;
};
