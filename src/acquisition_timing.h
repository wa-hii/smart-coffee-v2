#pragma once

#include <stdint.h>

// Pure, platform-independent timing helpers for AVR and host simulation.
// Never make the next phase relative to when a sensor or LCD command finished:
// that introduces an extra 1Hz scheduler tick at every boundary.
namespace AcquisitionTiming {
inline uint32_t boundary(uint32_t phaseStartMs, uint32_t durationMs) {
  return phaseStartMs + durationMs; // intentional uint32_t wraparound
}

inline bool due(uint32_t nowMs, uint32_t phaseStartMs,
                uint32_t durationMs) {
  // Signed distance to the *target* handles both a future timestamp and
  // millis rollover, as long as the checked span is shorter than 2^31 ms.
  return static_cast<int32_t>(nowMs - boundary(phaseStartMs, durationMs)) >= 0;
}

inline uint32_t lateness(uint32_t nowMs, uint32_t phaseStartMs,
                         uint32_t durationMs) {
  return static_cast<uint32_t>(nowMs - boundary(phaseStartMs, durationMs));
}
} // namespace AcquisitionTiming
