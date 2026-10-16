# Audit akuisisi fisik Take Data 30 siklus — D-GAW_B41

**Waktu audit:** 16 Oktober 2026 WIB. **Sumber:** `data/raw/D-GAW_B41.csv` dari listener Nextion/ATmega COM5. **Status:** `STRICT_30_CYCLE_QA_PASS_NOT_LABEL_VERIFIED`.

## 1. Bukti source, listener, dan struktur

- File mentah 110.700 byte, SHA256 `823bd619b7b0081497e7364bd32d1568c1797215f2603f20be5f4a8b941f6765`.
- Metadata UI: `sample_id=D-GAW`, `roast_level=dark`, `origin=Arabika Gayo Wine`, `batch_id=B41`. **Ini metadata pilihan operator, bukan bukti independen roast/origin/lot fisik.**
- Listener `logs/acquisition_service.log`: mulai **17:39:19 WIB** dengan `ACQ START`, dan **17:54:34 WIB** `ACQ COMPLETE ... rows=908`.
- Strict `validate_file(path, expected_cycles=30)` mengembalikan **[] (PASS)**; 30/30 run, semua urutan purging→collecting lengkap, semua indeks fase kontigu, tidak ada duplicate/missing sensor rows.
- **908 baris sensor:** 754 purging (25–26/run) dan 154 collecting (5–6/run). Jumlah nominal 900 pada 1 Hz bukan syarat jumlah absolut; ketidaktepatan titik tepi fase karena sampling asynchronous. Waktu `timestamp` first→last **907,000 detik**, sample gap min **999 ms**, median **1000 ms**, max **1001 ms**, tanpa interval di luar 900–1100 ms. Firmware timestamp adalah millisecond sejak boot, bukan waktu nyata.
- Sepuluh ADC lengkap **0 sel NaN, 0 ADC bernilai nol, 0 saturasi >=32767**; 0 metadata event row tersisip, 0 partial rows. Suhu **29,41–30,53°C** (rata-rata 30,01°C); kelembapan **53,00–58,13 %RH** (rata-rata 55,20 %RH). Kondisi lingkungan bervariasi selama pengambilan.

## 2. Metode audit sinyal

Untuk tiap run dan kanal, `baseline = median(lima ADC terakhir purging)`, `collect_mean = rata-rata ADC collecting`, `delta_mean = collect_mean - baseline`, `delta_peak = maksimum ADC collecting - baseline`. Drift baseline dari run 1 ke run 30 adalah `(baseline30-baseline1)/|baseline1| × 100%`. Metrik hanya deskriptif, bukan konsentrasi aroma maupun sensitivitas analitik terkalibrasi.

| Kanal | Drift baseline run 1→30 | Median ΔADC collecting, 30 run | Run ΔADC mean positif/30 |
|---|---:|---:|---:|
| TGS822 | +25,91% | +752,40 | 30 |
| MQ8 | +24,47% | +511,60 | 30 |
| TGS813 | +14,86% | +126,30 | 30 |
| TGS816 | +6,81% | +540,30 | 30 |
| TGS2620 | +2,68% | +408,50 | 30 |
| TGS2602 | −1,85% | +391,90 | 30 |
| TGS2611 | −3,00% | −0,85 | 10 |
| MQ135 | +0,58% | +1,20 | 23 |
| MQ3 | +0,52% | +0,30 | 16 |
| TGS2600 | +0,03% | 0,00 | 13 |

**Interpretasi:** TGS822/MQ8/TGS813 menunjukkan drift baseline naik besar selama sesi; sebelum menganggap 25 s purging cukup, uji blank/recovery, suhu/RH, kemungkinan residu aroma dan warm-up. MQ3/MQ135/TGS2600 dan TGS2611 mempunyai respons collecting rata-rata rendah/tidak konsisten relatif resolusi ADC yang tampak, bukan bukti kegagalan sensor. Respon TGS822 saat collecting berkurang dari +2530,4 ADC pada run 1 ke +417,4 pada run 30; MQ8 dari +1827,0 ke +300,2; perlu kajian kondisi chamber dan batch order.

## 3. False alarm validator setelah penyimpanan

Log memuat `Acquisition validation FAIL` sesaat **setelah** file sukses disimpan pada 17:54:34, dengan pesan `run_id harus 1..5 ...`. Root cause: fungsi `validate_completed_file()` (postpublish log-only) memanggil `validate_file(path)` dengan default lama **5 run**, walau validator staged pra-publish sudah memakai **30 run**. **File aslinya valid** pada 30 run; pesan FAIL tersebut bukan bukti data cacat. Diperbaiki di `scripts/lcd_acquisition_service.py` agar postpublish memakai `expected_cycles=30`. Regression `test_acquisition_integrity.py` kini memeriksa secara eksplisit bahwa logging PASS, bukan false FAIL, untuk file 30 siklus. **Listener yang sudah berjalan harus direstart saat benar-benar IDLE agar kode baru aktif**; audit tidak merestart maupun membuka COM5.

## 4. Keputusan QA dan tindak lanjut

- **PASS:** integritas raw, kontrak 30 siklus, 1 Hz yang stabil, ADS ADC non-missing, temperature/RH tersedia, autosave selesai.
- **REVIEW:** drift signifikan pada TGS822, MQ8, TGS813; beberapa kanal hampir tak berubah antar fase. Sebelum protokol produksi, uji recovery baseline/blank, stabilisasi sensor dan kontrol suhu/RH.
- **HOLD untuk ground-truth AI:** identitas kopi fisik, `physical_specimen_id`, lot, roast-batch dan bukti label origin/roast independen belum tersedia. 30 siklus **bukan 30 spesimen independen**; tidak boleh dijadikan blind test model final.
- **Data mentah tetap byte-identical.** Hasil per siklus: `results/b41_take30_audit_20261016/cycle_quality.csv`, `cycle_sensor_response.csv`, `sensor_quality_summary.csv`, `summary.json`; 10 grafik: subfolder `plots/`. Reproduksi: `scripts/audit_take30_b41.py` dan `scripts/plot_b41_sensor_qc.py` ke tujuan kosong tanpa overwrite.
