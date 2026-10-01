# ROAST SENSE – NX4827T043_011

Target: **NX4827T043_011**
Series: **Basic**
Resolution: **480 × 272 landscape**

This package is the model-specific implementation set for the ROAST SENSE e-nose UI.

## Folders
- `backgrounds_clean_bmp/` — import these 24-bit BMPs into Nextion Editor. Dynamic value areas are blank.
- `backgrounds_clean_png/` — PNG equivalents.
- `mockups_bmp/` / `mockups_png/` — visual reference with example values.
- `nextion_events/` — Touch Release code for Hotspot components.
- `component_map.csv` — exact page/object names and coordinates.
- `nextion_project_spec.json` — full machine-readable project mapping.

## Build in Nextion Editor
1. Create a new project and choose **NX4827T043_011**.
2. Set landscape 480×272.
3. Add 12 pages in this exact order:
   `pSplash`, `pHome`, `pTake`, `pDataRun`, `pDataDone`, `pTest`,
   `pTestRun`, `pResult`, `pCal`, `pSettings`, `pHistory`, `pAlert`.
4. Import the BMP files from `backgrounds_clean_bmp/`.
5. Put the matching image as a full-page Picture/background on each page.
6. Add only the dynamic Text/Progress objects listed in `component_map.csv`.
7. Add transparent Hotspot objects over every button region in `component_map.csv`.
8. Paste the corresponding Touch Release code from `nextion_events/`.
9. Generate the 3 fonts listed in `nextion_project_spec.json`.
10. Compile and verify every page in Nextion Simulator before uploading to the panel.

## Why this layout is intentionally shared across both 4.3-inch models
The UI stays inside the Basic-series component subset. That means the same ATmega/Raspberry Pi
state machine and UART protocol can be used on both target displays without maintaining two logic
branches.

## Acquisition flow
`pHome -> pTake -> pDataRun -> pDataDone`

- Labeled data acquisition: 40 cycles.
- Controller owns purge/collect timing and CSV naming.
- Nextion only displays state and reports user touches.

During `pDataRun`, `tSensors` is reused as a compact live sensor readout. The
firmware rotates through all ten ADC channels once per sensor refresh, for
example `MQ3:1234` or `TGS816:N/A`. Dedicated fields can be added later when
the HMI is revised and recompiled.

## AI test flow
`pHome -> pTest -> pTestRun -> pResult`

- User does not enter roast/origin for an unknown sample.
- ATmega performs sensor acquisition.
- Raspberry Pi 5 performs feature extraction + AI inference.
- Result page receives roast prediction, origin prediction, confidence, and probabilities.
- The current firmware populates the roast label when on-device inference is
  enabled. Confidence, origin, and class probabilities remain `N/A` until a
  verified result source provides those values.

## Baud
The package assumes 115200 baud for controller communication. Keep the editor/runtime setting and
the ATmega code consistent.
