# Grafik roast B33–B36: normalisasi t0 dan 12 warna

**Tanggal:** 18 Oktober 2026. **Cakupan:** perubahan plotting offline saja,
tanpa mengubah CSV, model, firmware, HMI atau output versi lama.

## Interpretasi grafik

Jalankan `scripts/plot_cross_roast_b33_b36.py` untuk menghasilkan
`results/plots_cross_roast_B33_B36_t0norm_multicolor_20261018/`.

- `01_overlay/`: kurva level dark/medium/light untuk batch B33–B36
  pada **origin dan kanal sensor yang sama** ditumpuk, sumbu X diukur
  relatif terhadap t0 masing-masing file.
- `02_merge_per_roasting/`: grafik per sensor menampilkan empat segmen
  batch B33 sampai B36. Batas segmen tidak dihubungkan secara kontinu.
  Garis vertikal kecil di setiap segmen menunjukkan posisi t0.
- Setiap kombinasi **level roasting × batch** memiliki warna berbeda
  (maksimal 12 warna), dilengkapi pola garis batch yang berbeda dan legenda.

**Definisi t0 untuk setiap file dan sensor:** sampel sensor terakhir dalam
`run_id=1, phase=purging`, tepat sebelum `run_id=1, phase=collecting`.

`x = indeks_baris_sensor - indeks_baris_sensor_t0`

`delta_ADC = ADC - ADC_pada_t0`

Oleh karena itu titik t0 selalu `(x=0, delta_ADC=0)`, fase purging pertama
sebelum t0 berada pada X negatif, dan collecting pertama mulai X=1.
Seluruh lima siklus dipertahankan; data tidak dipotong, ditambah atau
diinterpolasi. Indeks ini **bukan detik terkalibrasi**. Jumlah sampel purging
pertama dilaporkan apa adanya di `series_t0_diagnostics.csv` (dapat berbeda
sedikit dari 25 karena timing akuisisi).

## Provenance dan QC

Sumber B33–B36 diambil dari `data/raw/*.csv`; jika B36 tidak ada di root,
fallback arsip `data/raw/irul_B36_B37` hanya dipakai bila SHA256 cocok
manifest impor. `D-MING_B36.csv` arsip *HOLD* karena indeks `run 2 purging`
tidak kontigu: grafik MING hanya memiliki 11 dari 12 seri potensial.
Data `CAW` adalah kontrol udara bersih, bukan kopi; tidak ditampilkan.
Metadata origin TEM berbeda antar-roast (Temanggung vs Temanggung Mukidi),
sehingga tidak digabung. Data dan hasil sebelumnya dipertahankan.

Artefak hasil meliputi `plot_index.csv`, `summary.json`, `source_manifest.csv`,
`excluded.csv`, `missing_series.csv`, `series_t0_diagnostics.csv` dan PNG.
Grafik merupakan diagnostik eksploratif, bukan bukti label fisik atau hasil
uji AI yang independen.

## Perintah QA dan regenerasi

```powershell
python scripts/test_plot_cross_roast_b33_b36.py
python scripts/plot_cross_roast_b33_b36.py --output-dir results/plots_cross_roast_B33_B36_t0norm_REGENERASI
```

Skrip menolak menimpa folder hasil yang telah ada. Pengujian unit menguji
anchor t0, delta ADC, t0=0, first collecting x=1, keunikan warna,
pemilihan arsip dengan manifest hash, data HOLD dan preservasi CSV.
