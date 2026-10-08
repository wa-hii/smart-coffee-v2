# Smart Coffee E-Nose v2 — verified current state (2026-10-08)

> Authority: source code + offline QA + top-level raw B32–B35 files. This is an
> engineering snapshot, **not** a claim of live physical validation.

## Repository and scope

- Canonical checkout `smart-coffee-v2-hardware/smart-coffee-v2-hardware`, branch
  `wahyu`, starting HEAD `54d3321`. User-owned `platformio.ini` COM5 override
  existed before this audit and must remain untouched by commits.
- AVR production firmware: `src/`; Nextion canonical editable HMI:
  `nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI`.
  Figma `fix` frames are locked; existing TFT is not proven to represent them.
- Sensor order (firmware/CSV): TGS822, MQ135, **MQ3**, TGS2611, TGS2620,
  TGS2600, TGS2602, MQ8, TGS813, TGS816. Four ADS1115 0x48–0x4B; SHT30.
- Nextion communication: USART2 (`Serial2`) 9600 baud; MCU package PH0 pin 8
  RX2/D17 and PH1 pin 9 TX2/D16. USB host `Serial` 115200 baud.
- Active 5 cycles × (25 s purging + 5 s collecting), nominal ~150 s per test.
  Time includes additional UI/communication overhead, not yet bench-measured.

## Evidence and readiness

| Component | Verified | Outstanding |
|---|---|---|
| ATmega main firmware | `pio run -e mega2560` PASS; static RAM 3,720/8,192 B, flash 35,854/253,952 B before this audit's Python changes | Actual sensor/actuator timing, runtime stack/heap, warm-up, calibration, safe shutdown |
| Nextion firmware test | `pio run -e nextion_test` PASS | Live UART send/receive, restart and error states |
| HMI | 12 Figma assets, 12 HMI pages, 23 mapped events and transport contract PASS via offline verifier | Nextion Editor compile/simulator, newly compiled TFT and physical display |
| Acquisition | 86/86 B32–B35 CSVs structurally PASS with current validator | Sensor signal/ADC calibration, timestamp accuracy, specimen/session provenance |
| Data extraction | Candidate 62-feature schema, 86 file-level observations, no training performed | Scientific feature ablation, validation on unseen sessions |
| ML | B01–B05 historical RF results available | All B32–B35 train/validation/model promotion |
| Raspberry Pi 5 | Target architecture documented | Adapter implementation, Pi benchmark, live integration |

## Dataset inventory (top-level B32–B35 only)

- 86 files; B32=18, B33=20, B34=22, B35=26.
- 13,615 CSV rows: 13,003 complete sensor measurements + 612 historical
  metadata-only event rows; **zero partial rows** per structural validator.
- 10,756 purging + 2,247 collecting sensor rows. Zero missing temperature and
  humidity values in this specific set; zero ADC 0 or 32767 cells.
- Light=30, medium=28, dark=28 acquisition files; 23 observed roast-origin
  sample codes. There are nominally 430 five-cycle run groups, **not** 430
  independent coffee specimens.
- Three timestamp-suffixed B35 files are repeats/collisions from separate
  acquisition files; never deduplicate or count physical samples without IDs.
- `timestamp` = ATmega `millis()`, not wall-clock timestamp. Chronological
  session/day/physical specimen IDs are absent from the canonical CSV schema.
- Origin identity `D-TEM`, `M-TEM` and `M-MUK` has labeling nuance across
  earlier metadata definitions; origin taxonomy must be frozen before training.

## Critical issues

1. **P0 data integrity:** Previous listener wrote PHASE_CHANGE as CSV sensor
   row; fixed in `54d3321`. This audit adds strict live payload numeric checks,
   full-run duplicate detection, filename-collision handling, and regressions.
2. **P0 model pipeline:** Legacy `8_extract_features.py` expects MQ9 and at
   least 10 collecting samples per run; active MQ3 has approximately five.
   Legacy script now refuses mixed-schema extraction rather than silently
   overwriting prior processed artifacts. New candidate extractor is distinct.
3. **P0 evaluation validity:** Legacy 2026-08-24 Random Forest B01–B05 had
   baseline test accuracy 57.50% and tuned 55.00%; these numbers say nothing
   about B32–B35. The old training CV uses `StratifiedKFold` on correlated
   runs; its reported CV figures are **not** leakage-safe evidence.
4. **P1 timing review:** `adsCallback()` reads ADC before
   `processAcquisitionState()` changes phase and prints JSON **after** phase
   transition. Boundary ADC samples may be attributed to the new phase.
   Requires simulator/bench evidence before modifying live timing behavior.
5. **P1 readiness:** ATmega TinyML is off by default (`USE_ON_DEVICE_INFERENCE=0`);
   origin and confidence show N/A. No validated Pi inference-response loop yet.
6. **P1 protocol:** Event metadata currently lacks explicit unique acquisition
   ID, physical sample ID, wall clock, CRC/sequence acknowledgements and host
   result/error contract. Versioned protocol needed before deployment.

## Boundary of this audit

Only offline builds, parser/validation tests, HMI contract verification and
existing CSV inspection were performed. No COM5 access, listener restart,
EEPROM write, calibration, pump actuation, flashing, model training or live Pi
deployment. New feature outputs are candidate evaluation inputs, not a
deployment-certified model.

See: `01_MASTER_E2E_ROADMAP.md`, `03_AI_MODEL_RESEARCH_AND_EVALUATION.md`,
`04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md`, and `06_INDEPENDENT_AUDIT_QA_QC.md`.
