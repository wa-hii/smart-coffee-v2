<<<<<<< HEAD
# Roaster-Control

Hardware program for the Smart Coffee Roaster Control System, running on ESP32
(PlatformIO / Arduino framework).

## What this firmware actually does

Current scope of `src/main.cpp` is **e-nose data acquisition + Nextion status
bridge**. It does *not* run the fuzzy-logic roasting control loop — the
`FuzzyController`, `RelayRegister`, `MAX6675_library`, `DFRobot_MLX90614`,
`ESP32_Servo` and `NextionInterface` libraries in `lib/` exist in the repo but
are **not wired into `src/main.cpp`**. If you're picking this project up,
that control loop (temperature sensing + heater/servo actuation via fuzzy
logic) still needs to be implemented and integrated with the code below —
don't assume it already runs on the device.

What runs today:
- Reads 6 gas sensors (e-nose) + temperature/humidity, computes PPM per gas
  channel, and streams everything as one JSON line per sample over serial.
- Listens on the same serial line for short text commands (`#preheat`,
  `#charge`, `#light`, `#medium`, `#dark`, `#finish`) — typically sent by a
  host-side script/model — and reflects them as text + background color on a
  Nextion touch display.

## Hardware wiring

| Peripheral | Bus / Pin | Notes |
|---|---|---|
| ADS1115 #1 | I2C `0x48` (ADDR→GND) | ch0=MQ-135, ch1=MQ-3, ch2=MQ-137, ch3=MQ-138 |
| ADS1115 #2 | I2C `0x49` (ADDR→VCC) | ch0=MQ-2, ch1=MQ-136, ch2=TGS822, ch3=TGS2620 |
| SHT31 (temp/humidity) | I2C `0x44` | |
| Valve PWM | GPIO 27 (`IN_VLV0`) | LEDC ch0, 5 kHz, 8-bit |
| Pump PWM | GPIO 23 (`SC_IN`) | LEDC ch1, 5 kHz, 8-bit |
| PC / host link | `Serial` @ 115200 | JSON sensor data out, `#command` text in |
| Nextion display | `Serial2` @ 9600 | status text/color only (waveform push is currently disabled, see `USE_NEXTION_GRAPH`) |

Wire both ADS1115 boards on the same I2C bus (they're distinguished by
address, not by separate buses).

## Build & flash

Requires [PlatformIO](https://platformio.org/) (CLI or VS Code extension).

```bash
pio run                # build
pio run -t upload       # flash to the ESP32
pio device monitor -b 115200   # watch JSON output (matches monitor_speed in platformio.ini)
```

## First-time gas sensor calibration (do this before trusting any PPM value)

The gas sensors need a per-device R0 baseline stored in flash (NVS,
namespace `enose_r0`). A fresh board (or one that's had flash erased) has no
baseline yet, and the firmware will now refuse to run with an explicit error
instead of silently reporting garbage PPM values.

1. In `src/main.cpp`, set `#define IS_CALIBRATING_GAS_SENSOR 1`.
2. Flash and power up the board **in clean, still air** (no coffee, no
   solvents/alcohol nearby) — this is what "R0" is measured against.
3. Let it run once through `setup()`; it prints
   `{"info" : "calibration done"}` and writes R0 values to NVS.
4. Set `IS_CALIBRATING_GAS_SENSOR` back to `0` and reflash. From now on the
   board loads the stored R0 values on every boot.

If you skip this and boot with `IS_CALIBRATING_GAS_SENSOR = 0` on an
uncalibrated board, you'll see:
```json
{"error" : "Gas sensors not calibrated yet. Set IS_CALIBRATING_GAS_SENSOR to 1, reflash once in clean air, then set it back to 0."}
```
repeating on serial — that's the fix above, not a hardware fault.

Other startup errors and what they mean:
- `{"error" : "SHT31 ERROR!"}` — temp/humidity sensor not found on I2C (check wiring/address `0x44`).
- `{"error" : "ADS 1 ERROR!"}` / `"ADS 2 ERROR!"` — the corresponding ADS1115 not found at `0x48`/`0x49`.

## Reading the e-nose data yourself

Every sample is one JSON object per line on the PC serial link (115200 baud). Example fields:

```json
{
  "adc_mq135": 12345, "adc_mq136": 0, "...": "raw 16-bit ADC readings",
  "temp": 24.8, "humidity": 55.2,
  "mq135_co": 1.2, "mq135_alcohol": 3.4, "mq135_co2": 410.0, "mq135_toluen": 0.1, "mq135_nh4": 0.2, "mq135_aceton": 0.0,
  "mq136_co": 0.0, "mq136_nh4": 0.0, "mq136_h2s": 0.0,
  "mq137_co": 0.0, "mq137_ethanol": 0.0, "mq137_nh3": 0.0,
  "mq138_benzene": 0.0, "mq138_hexane": 0.0, "mq138_co": 0.0, "mq138_alcohol": 0.0, "mq138_propane": 0.0,
  "mq2_h2": 0.0, "mq2_lpg": 0.0, "mq2_co": 0.0, "mq2_alcohol": 0.0, "mq2_propane": 0.0,
  "mq3_lpg": 0.0, "mq3_ch4": 0.0, "mq3_co": 0.0, "mq3_alcohol": 0.0, "mq3_benzene": 0.0, "mq3_hexane": 0.0,
  "tgs822_methane": 0.0, "tgs822_co": 0.0, "tgs822_isobutane": 0.0, "tgs822_hexane": 0.0, "tgs822_benzene": 0.0, "tgs822_ethanol": 0.0, "tgs822_acetone": 0.0,
  "tgs2620_methane": 0.0, "tgs2620_co": 0.0, "tgs2620_isobutane": 0.0, "tgs2620_h2": 0.0, "tgs2620_ethanol": 0.0
}
```

Set `#define USE_PPM 0` in `src/main.cpp` if you only want raw ADC values
(smaller/faster JSON, no per-gas PPM math).

Quick way to try it from a PC with the board plugged in over USB:

```bash
pip install pyserial
python3 - <<'EOF'
from scripts.SerialHandler import SerialHandler
h = SerialHandler(port="/dev/tty.usbserial-XXXX", baud=115200)  # adjust port
while True:
    print(h.read())
EOF
```
(On Windows/Linux, adjust the port to `COM3`, `/dev/ttyUSB0`, etc.)

To send a display status command from the host to the board (e.g. once your
own logic decides the roast level), write the raw bytes over the same port:
`h.write(b"#medium;")` — commands must end with `;` and start with `#`.

## Known data caveat

`data/note.txt` documents that in the `arabica1`–`arabica5` sample sets, the
TGS2620 and TGS822 channels were wired/labeled swapped. If you're using
those specific CSVs for training/analysis, swap the two columns back before
use; sensor readings collected after that note was written should already be
correct per the wiring table above.
=======
# smart-coffee-v2
>>>>>>> a1cb6022b976725868572fc9d3fa2449d41f550b
