# Preflight dan bukti bench pasif — Tahap 1

**Tanggal pengamatan:** 9 Oktober 2026

**Branch kerja:** `wahyu`

**Metode:** read-only pada proses, log layanan autosave, dan satu CSV yang sudah terpublikasi. Tidak membuka COM5 dari agen, menghentikan proses, mengirim perintah ATmega, menyentuh EEPROM, mengubah firmware/TFT, atau menggerakkan aktuator.

## 1. Bukti host dan serial

- Script `scripts/status_lcd_autosave.ps1` menunjukkan `lcd_acquisition_service.py` melalui `pythonw.exe`, PID **16472**.
- Status layanan mencatat **connected**, port **COM5**, baud **115200** dengan waktu status `2026-10-09T17:10:05`.
- Log berisi kegagalan `COM5 FileNotFoundError` beberapa kali sebelum **CONNECTED** pada `17:10:05,774`. Kesimpulan: ada fase reconnect; perlu pengujian terkontrol bila mengukur keandalan koneksi.
- Log berisi `ACQ START` untuk **L-MING, light, Arabika Sumatra Utara, B32** pada `17:20:56,355`.
- Log berisi `ACQ COMPLETE` pada `17:23:30,799`, final CSV **150 rows**, lalu `Acquisition validation PASS` pada `17:23:30,827`.

Catatan: status layanan dan log membuktikan host menerima stream serial; **tidak membuktikan firmware aktif di board identik dengan commit terbaru** atau komunikasi Pi/Nextion telah diverifikasi secara independen.

## 2. Bukti CSV final yang diperiksa tanpa mengubah file

**File:** `data/raw/L-MING_B32_20261009_172056.csv`

**SHA256:** `0dbec4b2d19e1370bfe2c22ff358214a675b5bcba25cf88dcfebeb6dc9d5f986`

| Pemeriksaan | Observasi | Status |
|---|---|---|
| Validator canonical `validate_file` | Tanpa error | **PASS** |
| Jumlah sampel final | **150** baris sensor | **PASS** |
| Fase dan siklus | 5 siklus, setiap siklus **25 purging + 5 collecting** | **PASS** |
| `sample_idx` | Kontigu mulai 1–25 pada purge dan 1–5 pada collect setiap siklus | **PASS** |
| Interval timestamp MCU | **996–1004 ms**, rata-rata sekitar 1000 ms | **PASS** untuk kontinuitas sampling berbasis MCU |
| Kanal ADC | Tidak ada nilai kosong, nilai 0, atau 32767 | **PASS** untuk kelengkapan numerik |
| SHT30 dalam CSV | Suhu **26,61–27,28 °C**, RH **54,79–60,13%** | **PASS** rentang plausibel, **belum** kalibrasi fisik |
| Checksum dan file hasil | CSV final ditemukan dan SHA256 dicatat | **PASS** |
| Timestamp fisik valve/pompa | Tidak ada alat ukur atau observasi langsung dari agen | **NOT VERIFIED** |
| Kesesuaian build Git dengan firmware alat | Belum diperiksa melalui version identifier/foto/pembacaan perangkat | **NOT VERIFIED** |
| Navigasi fisik Nextion 12 halaman | Tidak ada observasi langsung | **NOT RUN** |
| Fault injection, recovery, SHT30 dicabut, power-loss | Tidak dilakukan; berisiko mengganggu akuisisi aktif | **NOT RUN** |
| Raspberry Pi UART/USB inferensi | Belum diterapkan/diuji (Tahap 7) | **NOT RUN** |

## 3. Alat bantu QA baru

- `scripts/bench_stage1_passive_qa.py` memverifikasi CSV final tanpa serial I/O atau modifikasi file; membandingkan 150 sampel ideal, 5 siklus, urutan `sample_idx`, rentang 900–1100 ms dan melaporkan checksum.
- `scripts/test_bench_stage1_passive_qa.py` menguji fixture valid, hilang sampel, timestamp terlalu pendek, dan penolakan file dalam `incomplete/` menggunakan direktori sementara.
- Hasil sesi aktual: **BENCH_STAGE1_PASSIVE_QA — CSV_INTEGRITY: PASS**; `HARDWARE_ACTUATOR_TIMING: NOT_VERIFIED_BY_CSV`; `FIRMWARE_VERSION_ON_BOARD: NOT_VERIFIED_BY_CSV`.
- **Regresi suite penuh (9 Oktober):** build PlatformIO dua environment **PASS**, kontrak HMI 12 halaman/23 event **PASS**, kontrak statis Tahap 0–1 **PASS**, regresi akuisisi dan fitur **PASS**, `compileall` serta `git diff --check` **PASS**. Inventaris terkini **87/87 CSV PASS** (bertambah satu file dari baseline 86), B32 khusus **18/18 PASS** pada validator legacy khusus tanpa menyertakan file berakhiran timestamp. Snapshot kandidat fitur 86 observasi tidak otomatis diekstraksi ulang.

## 4. Keputusan dan SOP lanjut

**Kesimpulan:** **PASS** pada gerbang **bench pasif/rekaman serial-CSV** untuk satu sesi. Status keseluruhan Tahap 1 tetap **SEBAGIAN / hardware GO belum ditetapkan**, karena belum ada bukti fisik fase, driver aktuator, identitas firmware, dan navigasi Nextion.

Terdapat listener aktif yang memiliki COM5; **jangan mengambil alih port**. Draf `docs/SOP_BENCH_TAHAP1.md` telah disiapkan untuk prosedur B01–B08. Setelah operator menyetujui waktu, ruang lingkup dan kontrol keselamatannya, uji aktif dapat dilakukan saat alat idle dengan rollback tersedia.

**Dataset B32–B35 historis dan HMI terkunci tidak dimodifikasi.** Jangan menganggap dataset baru sebagai spesimen independen atau hasil validasi AI.
