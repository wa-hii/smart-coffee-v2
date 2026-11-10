#include "../src/ai_rf30_return.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

int main() {
  using namespace AiRf30Return;
  char text[9]={};
  tokenHex(0xB1F503A9UL,text,sizeof(text));
  assert(strcmp(text,"B1F503A9")==0);
  uint32_t token=0;
  Roast roast=Roast::NONE;
  assert(decode("#rf30:B1F503A9:light",&token,&roast));
  assert(token==0xB1F503A9UL && roast==Roast::LIGHT);
  assert(decode("#rf30:B1F503A9:medium",&token,&roast) &&
         roast==Roast::MEDIUM);
  assert(decode("#rf30:B1F503A9:dark",&token,&roast) &&
         roast==Roast::DARK);
  const char *invalid[]={
      "#rf30:B1F503A9:DARK", "#rf30:00000000:light",
      "#rf30:B1F503A9:unknown", "#rf30:B1F503A9:light;",
      "#rf30:B1F503A9:light\n", "#rf30:B1F503A9:lig",
      "#rf30:b1f503a9:dark", "#rf30:B1F503A:light",
      "#rf30:B1F503A9:medium:another", "light", "", "#start",
  };
  for (unsigned int i=0;i<sizeof(invalid)/sizeof(invalid[0]);++i) {
    assert(!decode(invalid[i],&token,&roast));
  }
  assert(!decode(nullptr,&token,&roast));
  assert(!decode("#rf30:B1F503A9:light",nullptr,&roast));
  assert(!decode("#rf30:B1F503A9:light",&token,nullptr));
  printf("RF30_NATIVE_RETURN_PROTOCOL_PASS\n");
  return 0;
}
