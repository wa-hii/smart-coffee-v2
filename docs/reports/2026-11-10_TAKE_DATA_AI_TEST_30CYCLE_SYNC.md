# Penyamaan 30 siklus: Nextion AI Test ↔ Take Data ↔ ATmega ↔ Pi 5

**Tanggal:** 10 November 2026

**Branch:** `wahyu`
**Status:** SOURCE+OFFLINE QA; **BELUM DI-FLASH / BELUM UJI E2E FISIK**

## Keputusan pengguna

Pertahankan model Random Forest 500 pohon yang dilatih dengan data 30
siklus (176 sesi menurut metadata peneliti). **Samakan AI Test dan Take
Data: 30 siklus, setiap siklus purging 25 s kemudian collecting 5 s.**
Durasi nominal 900 s/15 menit, 750 sampel purging + 150 sampel
collecting = 900 pembacaan per kanal/sesi, dengan sampling 1 Hz.

## Implementasi pada source

1. `src/main.cpp`: konstanta `ACQ_DATA_REPETITIONS=30`, sedangkan
   `ACQ_AI_REPETITIONS=ACQ_DATA_REPETITIONS`. Kedua mode mengikuti
   state machine dan timing yang sama. BUILD ID menjadi
   `take30-ai30-rfhost-20261110`, `FW_HELLO` mengumumkan 30 untuk kedua
   mode. Ini memudahkan verifikasi apakah perangkat masih memakai
   firmware lama; marker source **bukan bukti firmware terpasang**.
2. `pTestRun` menggunakan perhitungan progres dari `ACQ_REPETITIONS`
   dengan total 900 s; perkiraan awal 15:00. `pDataRun` tetap memakai
   `ACQ_REPETITIONS` sehingga sekarang keduanya sama-sama 30.
   Label `tFw` menjadi `DATA30-AI30`. Tidak ada modifikasi visual
   file .HMI, aset Figma, TFT atau Nextion fisik.
3. `scripts/stage7_bridge.py` default menerima 30 × (25+5) lengkap,
   900 sampel dengan indeks fase/siklus dan timestamp berurutan.
   `scripts/stage7_pi_adapter.py` mendeteksi identitas firmware baru,
   menyediakan batas listener read-only 1.260 s untuk durasi 900 s
   ditambah waktu operator. Perubahan ini **tidak** memberikan izin
   membuka serial tanpa SOP dan opsi persetujuan yang ada.
4. **Tes historis lima siklus tetap tersedia** hanya melalui
   `LegacySessionBridge(expected_cycles=5)`; tidak memenuhi
   kontrak aktif 30 siklus ataupun model RF500.
5. `validate_acquisition.py` membedakan CSV historis B32–B37 (5
   siklus) dan batch B41+ (30 siklus); untuk kelompok 30 mewajibkan
   900 titik tepat dan 25/5 setiap fase. Lima file tidak sesuai
   di akar `data/raw` secara eksplisit di-**exclude** dengan nama+
   SHA256 (lihat daftar di bawah), tidak diubah maupun diinterpolasi.

## Model tetap identik dengan yang diunggah

Manifest kandidat `models/roast_rf30_candidate_manifest.json` dan
`scripts/roast_rf30_pi_inference.py` tetap menggunakan fitur
`tgs822_max_mean`, `tgs822_purging_mean_mean`, dan
`mq8_max_mean` dari **ADC absolut** 30 siklus. Tidak ada baseline
subtraction atau fit Z-score yang disisipkan; tidak ada retraining.
Metadata menyebut OOB=83,52% dan weighted nested CV=80,11%
(176 sesi), tetapi pembagian grup dan generalisasi pada perangkat belum
diverifikasi. Prediksi hanya berlaku untuk rekaman 30 siklus lengkap.
Binary joblib tidak dimasukkan Git dan tidak dipakai dalam pengujian ini.

## Kesesuaian firmware, hardware dan Nextion

- Nextion `EVT:AI_START` → ATmega `ACQ_START mode=ai_test`,
  `cycles_total=30` → 30 × purge+collect → `ACQ_COMPLETE
  cycles=30,total_samples=900`.
- Take Data menghasilkan pola yang identik, tetapi menyertakan label
  operator untuk penyimpanan CSV. **Label tidak pernah diteruskan
  sebagai masukan AI Test**.
- USB `Serial` ATmega @115200 ke Raspberry Pi 5, Nextion
  `Serial2` @9600 ke ATmega. Fungsi pi `stage7_pi_adapter` masih
  **read-only/diagnostik**, bukan inference listener yang sudah
  mengirim hasil balik. `roast_rf30_pi_stream_replay.py` menerima log
  NDJSON 900-sampel yang direkam sebelumnya, dan
  `roast_rf30_pi_inference.py` menerima CSV 900-sampel.
- Firmware saat selesai AI Test masih menampilkan halaman `pResult`
  dengan `tRoast=N/A` (dan origin/confidence N/A). Hasil RF belum
  ditulis ke Nextion. Perlu protokol balasan Pi→ATmega, identitas sesi
  dan timeout/abort supaya model tidak dapat mengirim hasil salah sesi.
  Protokol tersebut **belum diimplementasikan/diaktifkan**; tidak
  ada flashing yang dilakukan pada milestone ini.

## Validasi dan batasan

**QA PASS (offline):**

- `pio run -e mega2560 -e nextion_test` sukses dua environment:
  firmware Mega RAM 3.869 / 8.192 bytes; Flash 33.902 / 253.952 bytes.
- `scripts/test_30cycle_take_ai_sync.py`: dua mode lulus lengkap 900,
  firmware FW_HELLO/ID dan progress sinkron, AI Test 5 siklus dan
  gap frame gagal tertutup (*fail closed*). Stream berasal dari ADC
  kopi nyata yang **direplay sebagai frame**, bukan observasi hardware.
- `scripts/test_stage1_firmware_contract.py` dan
  `scripts/test_absolute_timing_firmware.py`: 900 detik/fase tepat,
  interval detik dijaga dan pengujian timing native PASS.
- `scripts/test_stage7_bridge.py`,
  `scripts/test_stage7_pi_adapter.py`,
  `scripts/test_stage8_offline_e2e.py`, dan
  `scripts/test_stage8_transport_integration.py`: tes historis G3
  lima siklus masih lulus dengan mode legacy eksplisit.
- `scripts/test_roast_rf30_pi_inference.py` dan
  `scripts/test_roast_rf30_pi_stream_replay.py`: tiga fitur asli
  konsisten dan data tidak lengkap ditolak; AI Test 30 siklus tanpa
  label diterima, AI Test berlabel ditolak; prediksi model asli belum
  dijalankan.
- `scripts/test_acquisition_suite.py`: **115 CSV diperiksa, 109 PASS,
  6 KNOWN_INVALID_EXCLUDED berbasis SHA256, 0 FAIL**. Validasi file
  30 siklus tidak melonggarkan syarat 900 titik. Pengecualian adalah
  arsip historis, bukan data yang dibolehkan untuk training.
- `nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py`:
  12 halaman/23 event, antarmuka Serial2 tetap konsisten.
- `scripts/test_12_page_take_data_contract.py`: validasi terhadap
  **HMI canonical pada HEAD** lulus. Ada file HMI kerja pengguna yang
  SHA-nya berbeda, **tidak disentuh dan bukan objek yang terverifikasi**.

**Pengecualian historis dengan checksum tetap:** `D-GAW_B41.csv`,
`D-GAW_B42.csv`, `M-GAW_B41.csv`,
`L-MING_B45.csv`, dan
`L-MING_B50_20261018_182003.csv` tidak memenuhi 900 titik/fase
25+5 tiap siklus. CSV lima siklus lama lain tetap valid untuk arsip
historis, **tidak** dapat digunakan oleh RF500 30 siklus. Clean air
`L-CAW_B34.csv` tetap pengecualian historis.

**Masih BLOCKED/NOT RUN:** pengujian 900 titik di ATmega fisik,
Pi live USB read/ DTR power safety, RF500 joblib inference di Pi nyata,
pengiriman hasil Pi→ATmega→Nextion, akurasi prospektif independen,
uji unknown/udara bersih, dan flashing firmware/TFT. Ini belum
termasuk persetujuan G0–G3 fisik. Jangan mengklaim otomatis tampil
LIGHT/MEDIUM/DARK di LCD sebelum handler balasan teruji.

## Contoh uji offline tanpa perangkat

```bash
python scripts/test_30cycle_take_ai_sync.py
python scripts/roast_rf30_pi_inference.py --input "data/dataset sorting/b/kept/D-CAT_B70.csv" --validate-only
python scripts/test_roast_rf30_pi_stream_replay.py
pio run -e mega2560 -e nextion_test
```

## Langkah kerja hardware selanjutnya (memerlukan SOP)

1. Periksa kondisi mesin idle, alat/port USB, PSU/backfeed, DTR/reset,
   keandalan transport dan checksum firmware/model.
2. Firmware baru hanya di-flash setelah review dan persetujuan SOP,
   lalu verifikasi `FW_HELLO` aktual (data=30, ai=30).
3. Uji 30 siklus penuh AI Test dan Take Data secara terawasi;
   kedua mode harus menghasilkan 900 frame berurutan, fase 25+5,
   time-to-complete ~900 s, progres LCD 100%, aktuator aman.
4. Bangun transport balasan Pi→ATmega yang fail-closed, dengan
   ID sesi, timeout, ACK/NACK, abstention/unknown dan pengujian LCD,
   lalu sambungkan `roast_rf30_pi_inference.py` setelah validasi model.
5. Baru promosikan model berdasarkan blind/prospective evaluasi,
   pengujian lintas ALAT_1/2/3, dan kalibrasi probabilitas.
