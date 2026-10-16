# Smart Coffee E-Nose — ATmega2560 COM5 upload 30-cycle firmware

**Tanggal:** 16 Oktober 2026 WIB. **Status:** FLASH + AVRDUDE VERIFY **PASS**; firmware boot serial verified; Nextion Take Data **belum dites 30 siklus secara fisik**.

## Preflight

- Branch `wahyu`; base commit `82ce4b6` (30 siklus data dan 5 siklus AI).
- USB COM5 terdeteksi `USB VID:PID=0403:6001`, FTDI FT232R, serial `A10KMM3SA`.
- Proses autosave `pythonw.exe` PID 17540 sedang `connected` ke COM5 dan sementara dihentikan **setelah memeriksa folder `.incoming` kosong**, agar upload tidak berebut port. File CSV existing tidak diubah.
- Perbaikan sebelum flash: indikator `tCycles` halaman pTake kini menggunakan `ACQ_DATA_REPETITIONS` (**30**) saat IDLE; indikator halaman Settings `tFw` menjadi `DATA30-AI5`. Firmware `SMART_COFFEE_BUILD_ID = take30-ai5-20261016`.

## Bukti upload dan verifikasi

Perintah: `pio run -e mega2560 -t upload --upload-port COM5`.

- PlatformIO environment `mega2560`; protocol `wiring`.
- AVRDUDE membaca **device signature `0x1e9801`** (ATmega2560).
- Flash **35.140 bytes written**; baca balik: **35.140 bytes verified**.
- `pio run` upload: **SUCCESS**.

Postflash serial read-only COM5@115200 (tanpa mengirim perintah sensor/aktuator) menangkap:

```json
{"event":"FW_HELLO","protocol":"legacy-json.v1","build_id":"take30-ai5-20261016","adc_channels":10,"data_cycles_total":30,"ai_cycles_total":5,"purge_s":25,"collect_s":5}
```

Saat boot juga terlihat perangkat I2C `0x44` serta ADS1115 `0x48`, `0x49`, `0x4A`, `0x4B` (4/4 ADS1115 terdeteksi). Tidak ada klaim semua 10 sensor stabil atau tombol Nextion/E2E fisik telah lulus berdasarkan boot log saja.

## Pemulihan listener

Setelah serial check, listener autosave dibuka kembali via `pythonw scripts/lcd_acquisition_service.py --port COM5 --baud 115200`, PID baru `24936`; status JSON terakhir menunjukkan **`connected`**, port `COM5`, baud `115200`. Tidak memulai `Take Data` atau `AI Test` secara otomatis.

## Status akhir dan lanjutan

- **Firmware fisik terbaru terbukti ter-flash, dibaca balik dan boot ID cocok.** Take Data menargetkan 30 × (25 s purge + 5 s collecting), sekitar 15 menit nominal. AI Test tetap 5 siklus.
- **Nextion actual button/HMI flow, kurva sensor 30 siklus, kualitas CSV akhir, dan kondisi pompa/valve**: NOT RUN. Butuh operator menekan Take Data pada LCD dan memantau fisik chamber/aktuator serta listener hingga COMPLETE. Jangan menjalankan sample roast atau promosi AI sebelum verifikasi ini.
- Data mentah, folder plot, HMI lokal yang sudah berubah, dan modifikasi `platformio.ini` tetap dipertahankan. Laporan tidak mengklaim backup firmware lama berhasil dibuat; rollback memerlukan build dan flashing versi sebelumnya yang kompatibel.
