# ROAST SENSE - Nextion NX4827T043_011

Target display: **NX4827T043_011 (Basic)**
Resolution: **480 x 272 landscape**
UART: **9600 baud, 8N1**
Controller in this integration: **ATmega2560 only**

The visual source of truth is the final Figma page fix in UI-ENOSE. The
12 exported frames are kept byte-identical in backgrounds_clean_png/ and
mockups_png/. Do not redraw, recolor, resize, or substitute those screens.

## Canonical project

Use project/RoastSense_NX4827T043_011_COMPILE_READY.HMI for the current final
build.

The latest 00_Splash Figma revision is patched directly into this canonical
HMI. Pages 01_Home through 11_Alert are not rebuilt, so manual text-size and
layout adjustments made in Nextion Editor remain preserved.

Because the canonical HMI has been manually saved by Nextion Editor, its page
blob packing is Editor-managed and may differ from the original binary
generator layout. Do not rebuild this file from the old HMI baseline. For
future visual-only revisions, patch only the relevant picture resource. The
final structural check is Nextion Editor **Compile**.

Do not compile the older RoastSense_NX4827T043_011.HMI or
RoastSense_NX4827T043_011_FIXED.HMI. The COMPILE_READY project removes the four
legacy pSplash objects and also neutralizes their four old page-load init
instructions, which otherwise produce Invalid Variables during Nextion Editor
compile.

This is the canonical editable Nextion Editor project. It is generated from an
Editor-created NX4827T043_011 container, the locked 480x272 Figma exports, and
the dynamic component/event map in this directory.

The old compiled TFT under build/ predates the final Figma sync and must not be
treated as the final UI. Open the canonical HMI in Nextion Editor, compile it
there, and upload the newly compiled TFT to the display.

## Reproducible HMI build

From the repository root run:

    python nextion/NX4827T043_011/tools/build_figma_fix_hmi.py --baseline nextion/NX4827T043_011/project/RoastSense_NX4827T043_011.HMI --images nextion/NX4827T043_011/backgrounds_clean_png --output nextion/NX4827T043_011/project/RoastSense_NX4827T043_011.HMI

The builder is idempotent. It verifies the target model CRC, all 12 page CRCs,
the directory checksum, mandatory dynamic components, and required EVT touch
events.

Full offline contract QA:

    python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py

That QA also verifies every HMI background against the locked final Figma
export and checks that every HMI event is represented in the ATmega firmware.

## Page order

1. pSplash - 00_Splash
2. pHome - 01_Home
3. pTake - 02_TakeData
4. pDataRun - 03_DataRun
5. pDataDone - 04_DataDone
6. pTest - 05_StartTest
7. pTestRun - 06_TestRun
8. pResult - 07_TestResult
9. pCal - 08_Calibration
10. pSettings - 09_Settings
11. pHistory - 10_History
12. pAlert - 11_Alert

component_map.csv is the authoritative dynamic overlay/hotspot geometry.
nextion_events/ contains the corresponding Touch Release event source.

## Nextion -> ATmega protocol

Touch handlers emit one ASCII line using:

    prints "EVT:DATA_START",0
    printh 0D 0A

The ATmega parser only accepts printable ASCII plus CR/LF. Native binary
Nextion return packets are rejected. bkcmd=0 is also sent at boot to suppress
command-response traffic.

ATmega -> Nextion commands use the standard Nextion FF FF FF terminator.

## Wiring

- Nextion TX -> ATmega2560 **PH0/RXD2, physical MCU pin 8**
- Nextion RX -> ATmega2560 **PH1/TXD2, physical MCU pin 9**
- GND -> GND

On an Arduino Mega 2560 header these same USART2 signals are RX2/D17 and
TX2/D16. The production firmware therefore uses Serial2. Physical package pins
8/9 must not be confused with Arduino digital pins D8/D9.

## Take Data flow

pHome -> pTake -> pDataRun -> pDataDone

The ATmega owns all state:

- Roast Level up/down cycles through LIGHT, MEDIUM, DARK.
- Origin up/down cycles through the configured origin list.
- Batch ID uses minus/plus with minimum B01.
- Cycle count is read directly from ACQ_REPETITIONS in src/main.cpp.
- File name is generated automatically as roast-origin_Bxx.csv.
- Status becomes "Siap untuk pengambilan data" and START is enabled only when
  every required value is valid.
- PAUSE is a true pause/resume toggle; current phase and remaining time are
  preserved.

## Start Test flow

pHome -> pTest -> pTestRun -> pResult

This integration is intentionally ATmega-only. START AI TEST launches the same
sensor acquisition state machine in AI_TEST mode. When acquisition finishes,
the ATmega calls the existing on-device Inference module.

If USE_ON_DEVICE_INFERENCE is disabled or the local model cannot provide a
verified value, the result is shown as N/A. Origin, confidence, and class
probabilities also remain N/A unless a verified ATmega-side source exists.
No Raspberry Pi result is fabricated and no Raspberry Pi integration is added
by this workstream.

## Calibration, settings, history, and alerts

- CALIBRATION runs SensorArray::calibrate() only while acquisition is idle,
  stores R0 in EEPROM, reloads it, and refreshes the calibration screen.
- RESET resets UI selections and display brightness only. It does not erase
  sensor calibration.
- HISTORY stores the four latest UI summaries in ATmega RAM.
- The final Figma button is labelled EXPORT. The current HMI container keeps
  the legacy wire token EVT:HISTORY_CLEAR; firmware interprets it as
  non-destructive export to the USB debug Serial.
- RESULT SAVE exports the current local result to USB debug Serial.
- EXIT stops acquisition/actuators and presents a safe manual-power-off alert.

## Validation before flashing hardware

Run:

    pio run -e mega2560
    pio run -e nextion_test
    python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py

Then open the canonical HMI in Nextion Editor, compile it, exercise every page
in the simulator, and flash the newly generated TFT to the physical panel.
