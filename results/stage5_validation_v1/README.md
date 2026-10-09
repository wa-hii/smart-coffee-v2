# Tahap 5 — Validasi diagnostik offline (snapshot 9 Oktober 2026)

**STATUS: EKSPLORATORI / NO-GO IMPLEMENTASI UNKNOWN DI PERANGKAT.**
Seluruh file hasil adalah turunan saja, tidak mengubah CSV mentah, tidak
menyimpan model akhir, dan tidak mengaktifkan komunikasi Raspberry Pi.

Jalankan ulang ke direktori **baru**:

    python scripts/test_stage5_validation.py
    python scripts/stage5_validation.py --output-dir results/stage5_validation_v2

Input dan definisi model identik dengan Tahap 4:
`data/processed/stage3_v2/`, `data/analysis/stage2_v2/`,
`data/analysis/bench_only_exclusions.csv`.

| File | Keterangan |
|---|---|
| `heldout_probabilities.csv` | Prediksi per file dari 4 fold LOBO untuk 2 konfigurasi perbandingan, confidence **belum dikalibrasi** |
| `risk_coverage.csv` | Coverage dan kesalahan pada ambang **a priori** 0,0/0,5/0,6/0,7/0,8/0,9; per fold dan keseluruhan |
| `class_metrics.csv` | Precision/recall/F1 untuk dark/light/medium dan masing-masing batch |
| `calibration_diagnostic.csv` | Akurasi empiris vs confidence per bin; **bukan** confidence calibration |
| `batch_bootstrap.csv` | Bootstrap seluruh 4⁴ kombinasi pemilihan empat batch; **deskriptif**, sangat sedikit grup |
| `clean_air_surrogate.csv` | Output model kopi pada 5 file udara bersih berfitur valid; **bukan uji unknown coffee** |
| `clean_air_held.csv` | 1 file udara bersih yang gagal aturan akuisisi/fitur (CAW B34), disimpan apa adanya |
| `gain_stress.csv` | Simulasi perkalian relatif ADC 0,90/0,95/1,05/1,10 pada fitur terkait; **bukan hasil fisik drift** |
| `input_audit.csv` | Dukungan label dark/light/medium per batch |
| `config.json` | Hash input Stage 2/3, manifest exclusion, model/threshold/seed |
| `summary.json` | Status risiko, batas pengujian, larangan promosi |

**Peringatan penting:** confidence tinggi tidak menjamin benar atau dikenal.
Kelima sampel udara bersih diprediksi sebagai *light roast* oleh kedua
model; pada ambang 0,6 **tidak satu pun ditolak**. Ambang dalam CSV
**tidak dipilih/dioptimalkan** sebagai threshold produksi.
Pemilihan dua konfigurasi pembanding juga terjadi setelah melihat hasil
Tahap 4, sehingga metrik **tidak** merupakan evaluasi akhir yang unbiased.

Laporan keputusan: `docs/reports/2026-10-09_TAHAP5_GENERALISASI_UNKNOWN_QA.md`.
