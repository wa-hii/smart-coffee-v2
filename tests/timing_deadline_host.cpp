// Host-side executable regression of the SAME millis() helpers compiled by AVR.
// No actuator, LCD, COM port, dataset modification or real sleeping.
#include "../src/acquisition_timing.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

struct Result {
  uint32_t activeMs;
  int phaseCount;
  int purgeRows;
  int collectRows;
  uint32_t worstLatenessMs;
};

// Simulate an ADC hardware scheduler at stable 1Hz and a separate foreground
// dispatcher running with jitter due to serial event handling or UI work.
Result simulate(uint32_t initialTime, int cycles, int maxLoopStep) {
  const uint32_t phaseMs[] = {25000UL,5000UL};
  uint32_t now=initialTime, start=initialTime;
  uint32_t lastSampleDue=initialTime+250UL;
  int phase=0, cycle=1, transitions=0, purgeRows=0, collectRows=0;
  uint32_t worstLate=0;
  int iteration=0;
  for (;iteration<3000000;iteration++) {
    // Model an independent 1Hz sensor callback, with bounded jitter. Never
    // generate catch-up/fake samples in this model.
    if (AcquisitionTiming::due(now,lastSampleDue,0)) {
      if (phase==0) purgeRows++; else collectRows++;
      lastSampleDue+=1000UL;
    }
    if (AcquisitionTiming::due(now,start,phaseMs[phase])) {
      uint32_t late=AcquisitionTiming::lateness(now,start,phaseMs[phase]);
      if (late>worstLate) worstLate=late;
      assert(late<1000); // physical firmware would abort/quarantine
      start=AcquisitionTiming::boundary(start,phaseMs[phase]);
      transitions++;
      if (phase==0)phase=1;
      else if (cycle++==cycles)break;
      else phase=0;
    }
    // Deterministic alternating workload including a simulated Nextion/USB
    // scheduling gap; the phase start cannot be based on this workload.
    const uint32_t step=1U+static_cast<uint32_t>((iteration*37U)%maxLoopStep);
    now+=step;
  }
  assert(iteration<3000000);
  const uint32_t active=now-initialTime;
  const uint32_t expected=static_cast<uint32_t>(cycles)*30000UL;
  assert(active>=expected && active<expected+static_cast<uint32_t>(maxLoopStep));
  assert(transitions==cycles*2);
  // The ADC rate is 1Hz; all cycle boundaries have 25+5 seconds worth of
  // sensor opportunities instead of the old 26+6 dwell-time inflation.
  assert(purgeRows>=cycles*24 && purgeRows<=cycles*26);
  assert(collectRows>=cycles*4 && collectRows<=cycles*6);
  return {active,transitions,purgeRows,collectRows,worstLate};
}

int main() {
  for (int jitter : {1,11,80,250}) {
    const auto r=simulate(15000U,30,jitter);
    std::printf("DATA30 loop_jitter<=%dms completion=%lu ms transitions=%d P=%d C=%d late_max=%lu\n",
                jitter,static_cast<unsigned long>(r.activeMs),r.phaseCount,
                r.purgeRows,r.collectRows,static_cast<unsigned long>(r.worstLatenessMs));
  }
  const auto ai=simulate(3000U,5,250);
  assert(ai.activeMs>=150000UL && ai.activeMs<150250UL);

  // AVR millis rollover should not change the phase duration or deadline.
  const auto rollover=simulate(UINT32_MAX-12000UL,30,80);
  assert(rollover.activeMs>=900000UL && rollover.activeMs<900080UL);

  // Pause time does not count as active time. When resuming after 7.5sec,
  // existing firmware shifts acqPhaseStartMs by exactly that pause time.
  uint32_t firstStart=200000U;
  uint32_t pauseAt=firstStart+3200U;
  uint32_t pauseElapsed=pauseAt-firstStart;
  uint32_t resumeAt=pauseAt+7500U;
  uint32_t revisedStart=resumeAt-pauseElapsed;
  assert(!AcquisitionTiming::due(resumeAt,revisedStart,25000UL));
  assert(AcquisitionTiming::due(resumeAt+(25000UL-pauseElapsed),revisedStart,25000UL));
  assert((resumeAt+(25000UL-pauseElapsed))-firstStart==32500UL);

  // A 1.25 second stall is quality-invalid: never "compress" a phase
  // and silently issue a complete 30-cycle dataset.
  uint32_t start=12345U;
  uint32_t now=start+26250U;
  assert(AcquisitionTiming::due(now,start,25000UL));
  assert(AcquisitionTiming::lateness(now,start,25000UL)>=1000UL);
  std::puts("ABSOLUTE_900S_ADC_1HZ_PAUSE_WRAP_QUALITY_GATES_PASS");
}
