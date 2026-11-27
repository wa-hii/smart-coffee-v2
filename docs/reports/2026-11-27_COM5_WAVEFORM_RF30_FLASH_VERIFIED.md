# COM5 Waveform RF30 deployment — 27 November 2026

Operator confirmed V7 physical LCD test success on the prior device and requested
deployment of firmware de053ec6 to the other PCB connected to Windows COM5.
COM5 identity FTDI A10KMM3SA, VID:PID 0403:6001, ATmega2560 signature
0x1e9801. Historical Linux ID A10KMM3S. Receiver pinned to A10KNJBLA
left running; incoming folder empty at preflight. No other PCB flashed.

Used exact frozen `fix/atmega2560/firmware.hex`, profile
mega2560_waveform_rf30, source de053ec6, 36,392 application bytes,
SHA256 ae5b34eca58e68837f318308a8d8f7ab5db37380cd233a7e1b61361593216621.
All 46 frozen manifest files passed integrity check before deployment.
Guarded deployment script `scripts/com5_waveform_rf30_deploy.py`.

Fresh board-specific backup at
`private/com5_waveform_rf30_deploy/20261127_215644_183163/`.
Full logical flash 262,144 bytes (738 omitted suffix bytes independently
read as FF) and EEPROM 4,096 bytes; both independently verified against
the device before writing. Original flash SHA256
6b0b1db30419c748365fbd90fb3357e26001cd82fa0135d688788770c409886c;
EEPROM SHA256 a1f1161f0af472c902873d1050eb5f1813e883d27f823ca959ab22b9fb40c769.
Backup restoration was not physically tested. Never copy board-specific EEPROM
to a different PCB.

AVRDUDE flash-only upload with -D exit 0; independent verify 36,392 bytes
exit 0; full 4,096-byte EEPROM compare after upload exit 0, unchanged.
Manifest FLASH_AND_EEPROM_VERIFIED. No fuse, lockbit or EEPROM write requested.

Passive UART capture at 115200 after one 140 ms DTR reset received 991 bytes,
zero UART TX bytes. FW_HELLO legacy-json.v1, build take30-ai30-rfhost-20261110,
10 ADC channels, 30 cycles each mode, 25s purging and 5s collecting. ADS1115
4/4, Serial2 9600, System Ready. Calibration missing warning remains present;
unchanged EEPROM is verified, but sensor calibration validity is not proven.

Nextion V7 physical success on prior device is operator-reported. COM5 TFT
upload, physical navigation, acquisition and Pi integration are still pending;
only Basic NX4827T043_011 may use the frozen V7 TFT. No modification to the
running first Pi, its FTDI binding, model, datasets or HMI. RF500 medium/dark
classification accuracy remains unresolved. No automatic calibration or
acquisition started on COM5.
