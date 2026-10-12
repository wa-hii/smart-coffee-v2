# Riset keselamatan USB Raspberry Pi 5 dan E2E Tahap 8

**Tanggal:** 12 Oktober 2026
**Status:** riset literatur primer dan diagnostik Pi read-only **PASS**;
Tahap 8 E2E **OFFLINE MOCK PASS** dari CSV asli; kelistrikan PCB
custom, komunikasi serial fisik, inferensi AI, dan hardware E2E
**BELUM LULUS / NO-GO**.

## 1. Kondisi fisik dan batas kewenangan

Konfirmasi operator: **ATmega2560 pada PCB custom memiliki adaptor
power tersendiri**; **Raspberry Pi 5 memiliki adaptor lain**.
Kedua board dihubungkan **kabel USB langsung untuk komunikasi**,
tidak ada GPIO UART Pi ataupun TTL jumper FT232 ke header 40-pin.
Di Pi terenumerasi FTDI FT232R melalui USB-serial device
`/dev/ttyUSB0`; sumber data firmware memakai
`Serial` 115200, Nextion `Serial2` 9600.

Operator meminta riset objektif, dan menyetujui pengujian
lanjutan **jika** aman. Kondisi `PCB custom` belum memiliki
schematic/foto jalur power USB (VBUS) yang diverifikasi,
sehingga syarat aman untuk membuka serial/menjalankan
aktuator **belum dapat dibuktikan**. Tidak dilakukan
`open(/dev/ttyUSB0)`, flashing, penggunaan DTR/RTS,
perubahan OS, Nextion command, atau aksi pompa/valve.

## 2. Sumber primer dan analisis keselamatan

1. **Raspberry Pi Documentation — Raspberry Pi computer hardware, USB
   power/back-powering**:
   https://www.raspberrypi.com/documentation/computers/raspberry-pi.html
   Raspberry Pi 5 membatasi arus total periferal USB
   **600 mA pada konfigurasi suplai 3 A** atau
   **1,6 A bila catu 5 V/5 A yang memadai terdeteksi**.
   Dokumentasi menyatakan perangkat USB tidak boleh
   memberi arus balik ke host. Back-powering bisa
   melewati rangkaian proteksi Pi dan berisiko pada
   kondisi gangguan daya.
2. **Raspberry Pi 5 USB Power Delivery — white paper**:
   https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-009856-WP-1-USB%20Power%20delivery%20on%20Raspberry%20Pi%205.pdf
   Mode 5 V/5 A menyediakan budget periferal
   maksimum 1,6 A; ini batas keluaran host, **bukan
   jaminan aman ketika perangkat custom memberi daya
   secara terbalik ke port host**.
3. **FTDI FT232R Datasheet — self-powered configuration, section 6.2**:
   https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf
   Self-powered device diizinkan dan dapat dipakai
   dengan host USB, **asal USB VBUS diindera/diatur
   dengan benar dan tidak memaksa arus ke upstream**.
   Contoh skema FTDI menggunakan VBUS untuk
   RESET#/deteksi host. FT232R terdeteksi di Pi
   **tidak membuktikan PCB mengikuti skema**.

**Analisis:** penggunaan port USB Pi untuk
perangkat yang punya PSU terpisah **merupakan
arsitektur normal dan secara umum valid**.
Risiko sebenarnya ada pada implementasi power
selection, FT232 VCC/VCCIO, jalur VBUS,
proteksi balik, kabel dan rail beban board custom.
Tersambung/terenumerasi, OS tidak crash,
`throttled=0x0`, dan tidak adanya log error
**tidak cukup untuk membuktikan tidak ada backfeed**.
Klaim “USB hampir selalu aman” benar untuk
produk USB compliant yang terancang baik,
tetapi belum dapat dipastikan pada PCB custom
tanpa skematik/inspeksi fisik.

## 3. Diagnostik Pi 5 yang benar-benar dilakukan

SSH read-only `enose-v3@enose-pi5` via Tailscale:

| Item | Hasil pada saat pemeriksaan |
|---|---|
| Antarmuka | FTDI FT232R, `ftdi_sio`, USB 12 Mbit/s |
| Node Linux | `/dev/ttyUSB0`, by-id `usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0` |
| Power config | `vcgencmd get_config usb_max_current_enable` → `usb_max_current_enable=1` |
| Throttling | `vcgencmd get_throttled` → `throttled=0x0` |
| Owner saat `fuser` | tidak ada proses yang ditemukan |
| Potongan log kernel boot yang diperiksa | `ftdi_sio` attached to ttyUSB0; tidak ditemukan pesan overcurrent atau undervoltage pada filter yang digunakan |
| Komunikasi data UART | **NOT TESTED**; ttyUSB0 tidak dibuka |

Konfigurasi USB maximum-current `=1` menunjukkan
mode arus maksimum diaktifkan, tetapi tidak
mengukur konsumsi board custom, tidak mengukur
arus balik VBUS, dan bukan sertifikasi keamanan.
Log kernel yang difilter juga tidak mencakup
setiap kemungkinan gangguan power.

## 4. Keputusan G0–G3

| Gerbang | Status |
|---|---|
| G0 identifikasi dua PSU dan port USB | **Diketahui** |
| G0 skematik VBUS, regulator, reverse-current, board/pompa | **BLOCKED**, belum ada bukti fisik/skematik |
| G1 kabel USB terpasang | **Dikonfirmasi operator**, bukan uji keselamatan |
| G2 serial read-only 115200 via `ttyUSB0` | **NOT RUN**, menunggu G0 selesai dan izin eksplisit |
| G3 pengambilan data dengan aktuator via Nextion | **NOT RUN**, persetujuan terpisah |
| Stage 9 perangkat fisik | **NOT RUN / NO-GO** |
| Stage 10 model validasi prospektif | **NO-GO** (hasil Tahap 5/6) |

Langkah G0 oleh hardprog/operator: identifikasi
PCB dan port power/adaptor, fotokan/lihat skema
VBUS USB dan jalur FT232R, cek proteksi backfeed
dan pemilihan daya saat PSU eksternal aktif.
Jangan melakukan eksperimen short, memotong VBUS,
atau cabut-colok berulang untuk menebak fungsi.
Gunakan `docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`.

## 5. Yang dapat dituntaskan aman: Tahap 8 E2E offline

Modul `scripts/stage8_offline_e2e.py` menjalankan
protokol lengkap **dalam simulasi**:

```text
Nextion mock AI_TEST / AMBIL DATA
  → event ATmega berbentuk JSON (direkonstruksi dari CSV asli)
  → parser + state tracker Tahap 7
  → pemeriksaan Stage6 NO-GO
  → keputusan AI N/A / kesalahan fail-closed
  → mock pResult=N/A (tidak mengirim ke MCU/Nextion asli)
```

Input adalah CSV **benar-benar diukur**
`data/raw/D-GAW_B33.csv`, SHA256
`d5e690f538a3967e2d07ded64903d284a348c1988bcc331a380dd50b0a8be819`.
Ada **151 frame sensor** (bukan nominal 150)
dan telah lulus batas toleransi fase Tahap 7.
Tidak ada sampel dummy untuk training;
kasus negatif merusak frame secara **in-memory
only** dan tidak mengedit CSV sumber.

Total **11 skenario**: AI_TEST positif,
9 negatif (`gap`, `duplicate`,
`invalid_json`, `stale_timestamp`,
`disconnect`, `missing_complete`,
`missing_adc`, `unapproved_inference`,
`premature_complete`),
dan pengambilan data berlabel (mock).
Sesi positif **COMPLETE_QA**, 151 baris
akuisisi berlabel diverifikasi terhadap
proyeksi skema CSV dalam memori; **tidak ada
file raw baru ditulis**. Semua negatif
berakhir **FAIL_CLOSED/N/A**, terminal
sesi tepat satu. Ground truth dari filename/
CSV tidak pernah menjadi input prediksi AI.
Model **tidak dipanggil**, karena release
gate Tahap 6 tetap NO-GO.

Pengujian dilakukan **dua kali pada platform berbeda**:

- Windows DevSpace `python scripts/test_stage8_offline_e2e.py`: PASS.
- Raspberry Pi langsung melalui SSH dengan `.venv`
  yang sama: **PASS**.
- JSON hasil Pi dibandingkan dengan JSON Windows:
  **IDENTIK** untuk input/data dan algoritma yang sama.
- Program baru dan input CSV memiliki hash SHA256 sama di
  Windows/Pi; bukti:
  `results/stage8_offline_e2e_v1/pi_remote_evidence.json`.

## 6. Status akhir dan langkah yang belum selesai

**Stage 8 — SIMULASI E2E OFFLINE PASS** (11/11 kasus);
**bukan** hasil end-to-end hardware.

### Regresi akhir lintas tahap (hasil aktual)

| QA yang dijalankan | Hasil |
|---|---|
| `test_stage8_offline_e2e.py` di Windows dan Pi | **PASS**, 11 kasus, dua jalur positif, 9 kasus negatif FAIL_CLOSED |
| `test_stage7_usb_contract.py`, `test_stage7_pi_adapter.py`, `test_stage7_bridge.py`, `test_stage7_pi_preflight.py`, `test_stage7_uart_preflight.py` | **PASS** |
| `test_stage6_release_gate.py`, `test_stage5_validation.py`, `test_stage4_model_benchmark.py` | **PASS**, keputusan rilis tetap NO-GO |
| `test_stage3_feature_pipeline.py`, `test_stage2_dataset_audit.py`, `test_stage2_plot_provenance.py` | **PASS** |
| `test_bench_stage1_passive_qa.py`, `test_stage0_contract.py`, `test_stage1_firmware_contract.py` | **PASS** |
| `test_acquisition_suite.py` | **89/89 CSV PASS pada validator struktur** |
| Verifikasi Nextion | **PASS**, 12 halaman dan 23 event |
| `pio run -e mega2560 -e nextion_test` | **2/2 SUCCESS**, tanpa flashing/upload |
| `python -m compileall -q scripts`, `git diff --check` | **PASS**, warning LF/CRLF informasional |

File konfigurasi lokal `platformio.ini` dan CSV mentah
pengguna tidak diubah atau masuk milestone commit.

**Stage 9 — HW NO-GO** sampai:
G0 rangkaian daya PCB custom ditutup,
G2 USB serial real ditest dengan izin,
G3 satu sesi Nextion diawasi operator,
komunikasi Pi→ATmega→Nextion diimplementasikan,
dan uji aktuator serta recovery benar-benar lolos.

**Stage 10 — AI release NO-GO** hingga ada
dataset lokal baru berlabel fisik dan
validasi coffee-vs-air, unknown,
drift dan hasil prospektif yang memadai.
Kopi/udara bersih dalam Tahap 5 pernah
gagal pada model roast-only; hasil simulasi
Tahap 8 **tidak boleh digunakan untuk
mempromosikan model**.

Perintah ulang:

```bash
python scripts/test_stage8_offline_e2e.py
python scripts/stage8_offline_e2e.py --input data/raw/D-GAW_B33.csv \
  --output results/stage8_offline_e2e_v2/evidence.json
```

Berikan **nama output baru** agar evidence
sebelumnya tidak ditimpa. Kedua perintah
tidak membuka port serial atau menulis
file mentah.
