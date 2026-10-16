# Flash baseline ADC 60 sampel dan restart listener COM5

**Status:** upload ATmega2560, AVRDUDE flash verify, serial FW_HELLO, serta listener COM5 **PASS**. Uji fisik tombol Calibrate/Start Calibration dan penulisan CSV baseline **belum dilakukan**.

## Cakupan dan preflight

- Proyek branch `wahyu`, source commit `bd5774f`.
- Port `COM5`, FTDI VID:PID `0403:6001`, serial `A10KMM3SA`, diidentifikasi sebelum upload.
- Listener lama `lcd_acquisition_service.py` pada PID `24936` menguasai COM5. Sebelum menghentikannya, diperiksa folder `data/raw/.incoming` dan `data/baseline/.incoming` **kosong**, log terakhir mencatat D-GAW_B41 selesai pukul 17:54 WIB.
- Firmware mendefinisikan `IS_CALIBRATING_GAS_SENSOR=0` dan tombol `EVT:CAL_START` memakai jalur baseline ADC, bukan pemanggilan `sensors.calibrate()` (penulisan R0 EEPROM).
- QA offline sebelum flash: `test_baseline_firmware_contract.py`, `test_baseline_recording.py`, `test_acquisition_integrity.py`, `test_take30_contract.py` **PASS**. `pio run -e mega2560` **SUCCESS**.

## Bukti upload dan boot

- Listener lama dihentikan saat tidak ada file staging; upload dilakukan dengan `pio run -e mega2560 -t upload --upload-port COM5`.
- AVRDUDE: `Device signature = 0x1e9801`, **32688 bytes written**, **32688 bytes verified**, PlatformIO **SUCCESS**.
- Pembacaan serial COM5@115200 read-only setelah upload menangkap `FW_HELLO`:

```json
{"event":"FW_HELLO","protocol":"legacy-json.v1","build_id":"baseline60-r0safe-20261016","adc_channels":10,"data_cycles_total":30,"ai_cycles_total":5,"purge_s":25,"collect_s":5}
```

- Serial boot mendeteksi SHT30 pada `0x44` dan 4/4 ADS1115 (`0x48`–`0x4B`). **Ini bukti enumerasi I2C, bukan bukti kualitas seluruh sensor atau prosedur kalibrasi fisik.**
- Serial juga menampilkan peringatan **kalibrasi R0 belum valid**. Hal ini sesuai versi penanda EEPROM baru (`0xA6` menggantikan legacy `0xA5`), sehingga R0 sebelumnya tidak diinterpretasikan ulang; tidak ada perintah kalibrasi ulang atau penulisan EEPROM yang dijalankan pada tugas ini. Mode ADC mentah tidak bergantung pada R0.

## Listener dipulihkan

- Listener versi baru dijalankan kembali sebagai `pythonw.exe` PID **9584** dengan `--port COM5 --baud 115200`.
- `logs/acquisition_service.status.json` menunjukkan `state=connected`, `port=COM5`, `baud=115200`, `pid=9584`; log mencatat **CONNECTED COM5**.
- Tidak menjalankan tombol Take Data, Start Calibration, AI Test, aktuator manual, atau serial command aktif dalam verifikasi ini.

## Pekerjaan pengguna berikutnya

Dengan alat IDLE dan chamber pada udara bersih yang terkontrol: buka **Calibrate → Start Calibration** pada LCD. Harapkan indikator `REC n/60` hingga `CAPTURE DONE`, lalu periksa berkas `data/baseline/BASELINE_*.csv` dan `.baseline_qc.json` serta log listener `BASELINE COMPLETE`. Periksa 60 sampel, rentang suhu/RH, nilai B0 tiap kanal, serta flag review drift. Keterangan CAPTURE DONE hanya mengonfirmasi akhir stream MCU, **bukan keberhasilan penyimpanan oleh host**.

File D-GAW_B41 tetap merupakan data kopi historis yang diambil **sebelum** baseline ini; jangan pasangkan baseline baru sebagai kontrol pra-pengambilan B41. Data mentah, konfigurasi PlatformIO/HMI lokal, dan arsip grafik tidak diubah.
