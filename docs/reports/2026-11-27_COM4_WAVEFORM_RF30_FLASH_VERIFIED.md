# COM4 Waveform RF30 deployment — 27 November 2026

Operator connected the custom PCB to Windows COM4 and explicitly requested
the previously described deployment process. FTDI VID:PID 0403:6001,
Windows serial A10KMZQJA (Pi by-id A10KMZQJ), signature 0x1e9801.
Receiver pinned to A10KNJBLA was not interrupted. Incoming data folder empty.
Pi supervisor was waiting for the disconnected FTDI, not changed.

Candidate profile mega2560_waveform_rf30, source commit de053ec6;
HEX SHA256 ae5b34eca58e68837f318308a8d8f7ab5db37380cd233a7e1b61361593216621.
36,392 application bytes; V5 HMI/TFT commit 2c16aa44.
Guarded script `scripts/com4_waveform_rf30_deploy.py` ran after authorization.
Fresh private backup `private/com4_waveform_rf30_deploy/20261127_162205_774808/`.
Full logical flash 262,144 bytes (738 omitted erased suffix bytes physically
read FF); EEPROM 4,096 bytes. Both compared against chip before write.
Original flash SHA256 850c56efcfd61cb97130f2c85e295bb537beed950865f5023367a0e6c4864913.
EEPROM SHA256 1591bf837dc368617fbc4f3460800b01255c1c34b2b3e1bbe72c2e8e06ce8e87.
Backup restore not physically tested.

AVRDUDE upload -D flash only: exit 0, 36,392 bytes written and verified.
Independent flash verify exit 0; full EEPROM compare after flash exit 0,
4,096 bytes verified unchanged. No EEPROM, fuse or lockbit writes requested.
Manifest FLASH_AND_EEPROM_VERIFIED. No manual actuator commands or acquisition.

Passive postflash UART via COM4, one controlled 140 ms DTR reset, 115200,
991 bytes received, zero UART TX bytes. Valid FW_HELLO: legacy-json.v1,
build_id take30-ai30-rfhost-20261110, 10 ADC channels, data/AI 30 cycles,
25s purge/5s collect. Nextion Serial2 9600 reported, ADS1115 4/4 detected.
Startup reports gas calibration missing and system ready; warning is NOT proof
that EEPROM changed. Do not reflash calibration mode or alter EEPROM without
separate investigation/authorization. Raw ADC readiness and acquisition
remain to be tested physically.

No TFT upload performed: physical LCD model and dedicated upload path not
confirmed. V5 TFT is for NX4827T043_011 Basic only; do not use on P series.
Do not run Take Data or AI Test with old TFT paired with new waveform firmware.
Pi reconnection, FW_HELLO reception by Pi and physical E2E remain pending.
The COM4 FW_HELLO establishes startup protocol but is not the Pi listener's
fresh FW_HELLO; exact firmware established by independent flash verify.
