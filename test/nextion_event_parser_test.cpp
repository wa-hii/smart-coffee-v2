#include <assert.h>
#include <string.h>

#include "../src/nextion_event_parser.h"

static void test_crlf_and_split_frame() {
  char storage[32] = {};
  char output[32] = {};
  NextionEventParser parser(storage, sizeof(storage));

  const char *frame = "EVT:DATA_START\r\n";
  for (const char *p = frame; *p != '\0'; ++p) {
    assert(parser.feed(static_cast<unsigned char>(*p)) == (*p == '\n'));
  }
  assert(parser.take(output, sizeof(output)));
  assert(strcmp(output, "EVT:DATA_START") == 0);
}

static void test_blank_line_and_overflow_are_ignored() {
  char storage[8] = {};
  char output[8] = {};
  NextionEventParser parser(storage, sizeof(storage));

  assert(!parser.feed('\r'));
  assert(!parser.feed('\n'));

  const char *tooLong = "EVT:TOO_LONG\n";
  for (const char *p = tooLong; *p != '\0'; ++p) {
    parser.feed(static_cast<unsigned char>(*p));
  }
  assert(!parser.take(output, sizeof(output)));
}

int main() {
  test_crlf_and_split_frame();
  test_blank_line_and_overflow_are_ignored();
  return 0;
}
