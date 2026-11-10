// 30-cycle RF result wire contract (UART USB Serial0).
// Host -> ATmega: #rf30:0123ABCD:light;
// The 8-hex token is a per-session CORRELATION ID, not authentication.
// NEVER treat token possession as proof that the model is validated.
#pragma once

#include <stdint.h>
#include <stdio.h>
#include <string.h>

namespace AiRf30Return {

enum class Roast : uint8_t { NONE = 0, LIGHT = 1, MEDIUM = 2, DARK = 3 };

inline const char *label(Roast roast) {
  switch (roast) {
  case Roast::LIGHT: return "light";
  case Roast::MEDIUM: return "medium";
  case Roast::DARK: return "dark";
  default: return "N/A";
  }
}

inline bool decode(const char *cmd, uint32_t *sessionToken, Roast *roast) {
  if (!cmd || !sessionToken || !roast) {
    return false;
  }
  const size_t length = strlen(cmd);
  if (length < 19 || length > 21 || strncmp(cmd, "#rf30:", 6) != 0) {
    return false;
  }
  uint32_t token = 0;
  for (uint8_t i = 6; i < 14; ++i) {
    const char c = cmd[i];
    uint8_t digit = 0;
    if (c >= '0' && c <= '9') digit = static_cast<uint8_t>(c - '0');
    else if (c >= 'A' && c <= 'F') digit = static_cast<uint8_t>(c - 'A' + 10);
    else return false;
    token = (token << 4) | digit;
  }
  if (cmd[14] != ':' || token == 0) return false;
  const char *name = cmd + 15;
  Roast parsed = Roast::NONE;
  if (strcmp(name,"light") == 0) parsed = Roast::LIGHT;
  else if (strcmp(name,"medium") == 0) parsed = Roast::MEDIUM;
  else if (strcmp(name,"dark") == 0) parsed = Roast::DARK;
  else return false;
  *sessionToken = token;
  *roast = parsed;
  return true;
}

inline void tokenHex(uint32_t token, char *out, size_t size) {
  if (!out || size < 9) return;
  snprintf(out,size,"%08lX",static_cast<unsigned long>(token));
}

}  // namespace AiRf30Return
