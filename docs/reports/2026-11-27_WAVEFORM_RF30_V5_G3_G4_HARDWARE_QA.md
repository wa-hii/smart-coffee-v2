# Waveform RF30 V5 hardware QA — 27 November 2026

Target: custom ATmega2560 FTDI A10KMZQJA (Windows COM4), A10KMZQJ
on enose-pi5, firmware profile mega2560_waveform_rf30, verified deployment
bdc31cac; HMI/TFT V5 2c16aa44. Operator confirmed physical TFT upload,
five-button Home navigation and moving native waveform. Operator replaced
the USB cable following earlier USB descriptor errors. Physical Cancel,
repeated AI sessions and fresh Pi FW_HELLO remain unverified.

## G3 labeled Take Data — PASS

L-MING_B01.csv in /home/enose-v3/smart-coffee-stage7/data/raw/; 99,585 bytes;
SHA256 d430ce88c4814f47ae5c6f618ca53155a1beedbb81073ff4a5de5bdfb9bbcabd
matches metadata. Started 18:10:48 WIB; saved 18:25:47 WIB. Independent CSV
audit: 900 rows, 20 columns, all 30 cycles and expected phase/sample indices,
750 purge / 150 collect, zero missing or duplicate rows/keys; all 10 ADC
channels finite, within 0..32767, no zero or full-scale readings. Timestamp
interval 998..1002 ms, mean 1000 ms. Temperature 30.06..30.63 C, humidity
54.90..60.27 percent. MQ135, MQ3 and TGS2600 weak response in this capture,
not proof of sensor fault. No imputation or dataset alteration.

## G4 physical AI Test — PASS for this single observed session

Operator reported LCD LIGHT. Pi log: 30 cycles, RF500_LIVE_CAPTURE_COMPLETE_900,
RF500_RESULT_READY_FOR_MCU_ACK, RF500_MCU_ACK_CONFIRMED roast=light, samples=900,
success_count=1, serial_kept_open=true. Session token 2F8B1BDB.
Archive `recordings/20261127T114703_115182Z_2F8B1BDB.ndjson` and JSON metadata,
recorded 18:47:03 WIB, capture SHA256
c545bd5d8f33ac29979ab0843c67176d9fb97e68f90bfd6623224c28eb412a9f matches.
Independent audit: 961 frames, 900 sensor rows, 750 purge / 150 collect,
30 cycles, 900 unique indices, no missing/invalid/zero/saturated ADC;
timestamp intervals 999..1002 ms (mean 1000); 900026 ms active, no pauses;
zero ground-truth label fields in capture. Offline replay with pinned RF500
predicts light, vote fractions light=1.0, medium=0, dark=0 (not calibrated
confidence). Features tgs822_max_mean=13072.7, tgs822_purging_mean_mean=12462.98,
mq8_max_mean=14162.933333333332. No serial transmission during replay.

## G5 reliability — PARTIAL

Same persistent listener PID 2104 completed G3 then G4 without restart.
No kernel USB/FTDI/undervoltage events found during 18:10:48..18:47:04 WIB;
last FTDI attachment 17:10:00 WIB; power throttled=0x0. Incoming directory
empty, G3 CSV SHA unchanged after G4; AI archive separate from training CSV.
Live multi-class/repeated AI testing, Pause/Resume, Cancel and recovery
remain pending. Fresh FW_HELLO on Pi not observed (COM4 postflash verified,
ACQ_START matches protocol). Calibration startup warning remains open.
This is engineering bench validation, not independent model accuracy or
production release approval. No firmware, model, data or Pi configuration
changed by this audit. Raw data and recordings remain on Pi.
