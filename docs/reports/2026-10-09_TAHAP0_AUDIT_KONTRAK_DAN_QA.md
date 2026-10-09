# Laporan milestone Tahap 0 — audit kontrak dan QA/QC

**Tanggal:** 9 Oktober 2026

**Proyek:** Smart Coffee E-Nose v2 / RoastSense

**Branch:** `wahyu`

**Baseline Git sebelum pekerjaan:** `bf7080e`

**Cakupan:** Tahap 0 pada `docs/01_MASTER_E2E_ROADMAP.md`.
**Pengujian:** offline saja; tidak ada koneksi port serial, flashing, EEPROM, aktuator atau TFT fisik.

## 1. Tujuan dan pemeriksaan

Mengidentifikasi sumber implementasi setiap subsistem dan kontrak data/hardware yang benar-benar berjalan, merekonsiliasi kode–dokumentasi–riwayat Git yang relevan, serta menyusun daftar risiko berikut pemilik tahap. Inspeksi mencakup `src/main.cpp`, `src/sensor.*`, `src/actuator.*`, `src/inference.*`, `src/nextion_transport.*`, skema dan listener Python, kolektor manual, HMI canonical, dataset B32–B35, model historis, dokumentasi dan perubahan lokal.

## 2. Temuan dan tindakan

| Temuan | Keterangan | Tindakan pada Tahap 0 |
|---|---|---|
| Dokumentasi pin Nextion salah | Kode/dokumen lama menyatakan TQFP PH0=8/PH1=9. Datasheet Microchip Figure 1-1 menetapkan **PH0=12/PH1=13**, header Mega D17/D16. | Koreksi narasi dokumentasi, pesan diagnostik boot, dan kontrak statis; **tidak mengubah sambungan**. |
| Komentar fase usang | Header `src/main.cpp` masih menyebut 180 s collecting dan 60 s purging serta TinyML seolah aktif. Implementasi memakai 25 s purging + 5 s collecting × 5 dan TinyML mati secara default. | Koreksi komentar; tidak mengubah nilai makro/state machine. |
| Label `AI_TEST` tidak dipisahkan | `ACQ_START` pada `ai_test` masih mencetak pilihan roast/origin layar. Listener hanya menyimpan `labeled_data`. | Catat T0-02 untuk Tahap 1/7; jangan gunakan label ini sebagai ground truth inferensi. |
| Diagnostik `#pin_scan` berisiko | Kode mengubah mode dan nilai pin, termasuk D19/RX1 dan D20/SDA. Berpotensi mengganggu Pi maupun I2C. | Tandai P0 T0-01, perlu hardening dan SOP sebelum bench test. |
| Metadata asal kopi belum dibakukan | Pemetaan sama pada 30 preset yang beririsan; kolektor manual memiliki `L-CAW`, `M-CAW`, `M-MUK` tambahan. Listener mempunyai fallback. Istilah TEM/MUK/CAW belum terkonfirmasi sebagai label ilmiah. | Catat untuk Tahap 2; tidak mengedit CSV historis. |
| Arsitektur Pi belum sesuai keputusan perangkat | Host produksi yang ada masih USB Serial `Serial` 115200; `Serial1` GPIO UART Pi belum diimplementasikan. | Catat dua alternatif transport untuk Tahap 7, termasuk kebutuhan level 5 V↔3,3 V dan cek skematik. |
| Sumber dokumen terpecah | Roadmap, README, firmware, dan panduan HMI menggunakan nomor pin dan penjelasan transport yang berbeda. | Tambahkan dokumen 02 sebagai acuan kontrak; selaraskan semua dokumen terkait. |

## 3. Hasil pengujian yang benar-benar dijalankan

| Perintah/pemeriksaan | Hasil | Bukti ringkas |
|---|---|---|
| `pio run -e mega2560 -e nextion_test` | **PASS** | Dua environment SUCCESS; firmware utama RAM statis 3.720/8.192 byte, flash 35.866/253.952 byte. Test RAM 541/8.192 byte, flash 5.062/253.952 byte. |
| `python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py` | **PASS** | 12 aset Figma terkunci, 12 halaman HMI, 23 event, Serial2 9600, tipe komponen sesuai. Peringatan Pillow `getdata` deprecated masih ada. |
| `python scripts/test_acquisition_suite.py` | **PASS** | Regresi payload/integritas PASS; 86/86 CSV B32–B35 valid. |
| `python scripts/validate_b32_acquisition.py` | **PASS** | 18/18 file B32 lolos. |
| `python scripts/audit_b32_dataset.py` | **PASS** | 86 CSV; 13.003 baris sensor, 612 baris metadata historis, nol baris sensor parsial. |
| `python scripts/test_feature_pipeline.py` | **PASS** | `B32_FEATURE_PIPELINE_REGRESSION_PASS`. |
| `python scripts/test_stage0_contract.py` | **PASS** | Durasi 25/5×5, baud, urutan 10 ADC, empat alamat ADS, JSON/CSV, pin TQFP, HMI dan konsistensi 30 preset beririsan. |
| `python -m compileall -q scripts` | **PASS** | Sintaks modul Python diperiksa. |
| `git diff --check` | **PASS** | Tidak ditemukan kesalahan whitespace; peringatan LF/CRLF merupakan normalisasi Git, bukan kegagalan. |

**Tidak dijalankan / di luar cakupan:** Nextion Editor Compile/TFT aktual, penggunaan COM5, pengukuran UART pada PCB, kalibrasi sensor, pengoperasian pompa/valve, training/benchmark model MQ3, integrasi Raspberry Pi nyata, dan pengujian prospektif. Status bagian tersebut **NOT RUN / BLOCKED**, bukan PASS.

## 4. Artefak dan keputusan

- **Kontrak lintas subsistem:** `docs/02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md`.
- **Tes statis deterministik:** `scripts/test_stage0_contract.py`.
- **Revisi sumber/acuan:** `src/main.cpp` (komentar dan teks diagnostik), `src/sensor.h`, `README.md`, `AGENTS.md`, `docs/00_CURRENT_STATE.md`, `docs/01_MASTER_E2E_ROADMAP.md`, `docs/04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md`, `docs/06_INDEPENDENT_AUDIT_QA_QC.md`, `docs/REPOSITORY_STRUCTURE.md`, panduan Nextion.
- **Perlindungan:** tidak memodifikasi CSV mentah, HMI/TFT biner, model historis, ataupun perubahan lokal `platformio.ini`. Tidak ada modifikasi perilaku hardware atau operasi fisik.

**Status final Tahap 0:** **SELESAI untuk audit dan dokumentasi baseline offline.** Keputusan yang bergantung pada hardware/label maupun perbaikan perilaku adalah risiko terbuka T0-01 s.d. T0-07; tidak boleh tertukar dengan persetujuan implementasi tahap berikutnya.

**Tindak lanjut terurut:** mulai **Tahap 1** dengan keamanan `#pin_scan`, isolasi label AI_TEST, serta regresi state/timing; lanjutkan keputusan definisi origin pada Tahap 2 dan pilihan UART/USB pada Tahap 7. Jangan melakukan pengujian fisik tanpa SOP yang disetujui.

**Referensi pin resmi:** [Microchip ATmega2560 datasheet, Figure 1-1](https://ww1.microchip.com/downloads/en/devicedoc/atmel-2549-8-bit-avr-microcontroller-atmega640-1280-1281-2560-2561_datasheet.pdf); [Arduino Mega 2560 pinout](https://docs.arduino.cc/resources/pinouts/A000067-full-pinout.pdf).
