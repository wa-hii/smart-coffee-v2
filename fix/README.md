# FIX — Waveform RF30 V5 (2026-11-27)

**Rilis acuan untuk perangkat dengan hardware/protokol yang sudah teruji. Bukan rilis model AI dengan akurasi tervalidasi.** Jangan menggunakan file kandidat lama ketika flashing alat lain.

## Identifikasi paket

| Bagian | File / identitas |
|---|---|
| Firmware flash | `atmega2560/firmware.hex` (36.392 byte aplikasi; Intel HEX 102.372 byte) |
| Source firmware | `atmega2560/source_de053ec6.zip` (ekstrak menjadi proyek PlatformIO tersendiri) |
| Environment | `mega2560_waveform_rf30` |
| MCU | ATmega2560, signature `0x1e9801`, 16 MHz |
| LCD | NX4827T043_011 **Basic**, 480 x 272, bukan Intelligent |
| HMI dan TFT | `nextion/RoastSense_NX4827T043_011_WAVEFORM_RF30_V5.*` |
| Runtime Pi | `raspberry_pi5/runtime/` (lima modul dari Pi yang benar-benar menjalankan G3/G4) |
| Boot Pi lama | `raspberry_pi5/deployed_enose_pi5/` (salinan persis, khusus host enose-pi5) |
| Boot alat lain | `raspberry_pi5/boot_supervisor_template.sh` (template baru, bukan rilis fisik teruji) |
| Checksum | `manifest.json`, verifikasi dengan `python fix/verify_release.py` dari repo |

Build ID serial tetap `take30-ai30-rfhost-20261110`; ID ini tidak unik untuk binary V5. Gunakan SHA-256 firmware untuk membedakan rilis. USB 115200 baud; Nextion Serial2 9600 baud. 10 ADC, 30 siklus, 25 purging + 5 collecting, 900 sampel. Waveform DataRun ID 11 dan TestRun ID 10. Hasil RF memakai `#rf30:<TOKEN>:<ROAST>;` dan `AI_RESULT_ACK`.

## Flash ATmega lain (setelah izin operator)

1. Verifikasi paket, model board, identitas FTDI dan COM yang benar (COM dapat berubah), serta pastikan alat idle. Jangan mengambil alih port listener aktif.
2. Baca signature dan buat backup Flash serta EEPROM perangkat target yang baru, lalu verifikasi backup. Jangan menyalin EEPROM alat lain. SOP yang pernah berhasil pada A10KMZQJA ada di `docs/reports/2026-11-27_COM4_WAVEFORM_RF30_FLASH_VERIFIED.md`.
3. Upload **hanya** `atmega2560/firmware.hex` ke MCU yang telah diverifikasi, dengan bootloader wiring 115200 bila kompatibel. Jangan memakai COM11 default di source ZIP sebagai identitas target. Verifikasi readback aplikasi dan EEPROM tidak berubah. Tidak mengubah fuse/lockbit.
4. Pasang TFT V5 hanya pada model Basic yang sesuai. Jangan jalankan akuisisi dengan TFT lama dan firmware waveform baru. Periksa boot UART, ADC dan navigasi fisik sebelum pengambilan data.

## Raspberry Pi 5 alat lain

ID USB yang didukung oleh listener saat ini (cocokkan dengan `ls -l /dev/serial/by-id/`, bukan nama ttyUSB0):

| Windows serial historis | ID Linux |
|---|---|
| A10KMZQJA | A10KMZQJ |
| A10KMM3SA | A10KMM3S |
| A10KN6X9A | A10KN6X9 |

ID lain harus diaudit sebelum perubahan allowlist. Jangan menjalankan dua receiver atau supervisor pada perangkat yang sama. Salinan `deployed_enose_pi5/` adalah bukti konfigurasi host lama dan **tidak boleh langsung dijalankan pada Pi lain** (path, username dan FTDI dikunci).

1. Salin direktori `raspberry_pi5/` lengkap ke direktori rilis pada Pi target; gunakan Python 3.13.5 dan lingkungan virtual terisolasi dengan `requirements-verified.txt` (versi aktual Pi). Ketersediaan paket pada Pi baru perlu diperiksa, tidak ada instalasi otomatis.
2. RF500 referensi lokal disimpan di `archieve/rf500_reference_not_validated/`. Salin model dan metadata ke direktori model terpisah di Pi hanya jika pengguna mengizinkan penggunaan model kandidat tersebut. File joblib tidak dipush ke Git; ambil dari arsip lokal yang checksum-nya cocok, jangan ambil model tidak tepercaya. Listener exact masih memerlukan model hash lama untuk boot; mengganti model membutuhkan validasi/pembaruan kontrak inference secara terpisah. Model ini salah mengklasifikasikan Medium dan Dark dalam pengujian 27 November.
3. Siapkan direktori data dan gunakan template dengan path absolut, ID target yang benar, serta persetujuan operator. Contoh berikut **bukan perintah yang sudah dijalankan**; ganti semua path dengan path aktual. `--check` tidak membuka UART maupun mendeserialisasi model.

```bash
bash /path/raspberry_pi5/boot_supervisor_template.sh --check A10KMZQJ /path/.venv/bin/python /path/model/final_model.joblib /path/model/final_model_info.json /path/data/raw
```

Setelah preflight lulus dan supervisor lama dihentikan dengan aman, ganti `--check` menjadi `--run` untuk uji terawasi. Template menjaga port pinned, lock per ID, dan retry 15/30/60/120 detik. Arsip AI masuk ke `~/.local/state/smart-coffee-waveform-v5/<ID>/recordings`; CSV labeled ke DATA_ROOT yang diberikan. Autostart cron hanya dipasang setelah pengujian target dan review crontab, menggunakan perintah `--run` dengan path absolut dan redirect log. Jangan jalankan sebagai root atau bersamaan dengan supervisor sebelumnya. Template baru hanya diuji offline, bukan pengganti otomatis konfigurasi Pi yang sekarang aktif.

## Status QA dan batas klaim

- Flash COM4 dan EEPROM preservation PASS; TFT V5 fisik, navigasi, waveform, G3 900/900, dan 3 sesi G4 masing-masing 900/900 dengan MCU ACK PASS.
- Klasifikasi Light benar, Medium dan Dark salah (semua LIGHT). Model RF500 adalah referensi diagnostik, bukan model final. G5, Cancel/Pause, warning kalibrasi, dan FW_HELLO pada Pi masih perlu validasi.
- Tidak ada perubahan firmware, konfigurasi Pi aktif, data, model aktif, atau upload LCD saat membuat paket ini. Sumber build asli dipertahankan untuk kompatibilitas skrip; `fix/` adalah titik acuan deployment. Versi lama di `archieve/` bukan pilihan default.
